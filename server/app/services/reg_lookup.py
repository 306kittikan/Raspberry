"""ดึงตารางเรียนของนักศึกษาจากระบบทะเบียนแบบสด ๆ ตอนที่มีคนถาม

ทำไมต้องดึงสด ไม่เก็บไว้ในฐานข้อมูล
  ตารางเรียนบอกได้ว่านักศึกษาคนนั้นอยู่ที่ไหนในแต่ละวันเวลา
  ถ้าเก็บของทุกคนไว้ในตู้ เครื่องเครื่องเดียวก็กลายเป็นฐานข้อมูล
  ตำแหน่งของนักศึกษาทั้งสาขา ซึ่งเป็นความเสี่ยงที่ไม่คุ้มกับประโยชน์
  ดึงมาแสดงแล้วทิ้งไปเมื่อจบเซสชัน ตู้จึงไม่เคยถือข้อมูลนี้ค้างไว้

  วิธีนี้เป็นสิ่งที่ผู้ทำชุดข้อมูลแนะนำไว้เองในไฟล์ timetable dataset

ข้อจำกัดที่ต้องรู้
  ต้องต่ออินเทอร์เน็ต ถ้าตู้ออฟไลน์จะใช้ข้อมูลในเครื่องแทน
  อ่านจากหน้าเว็บของระบบทะเบียนโดยตรง ถ้าเขาเปลี่ยนหน้าเว็บ ตัวอ่านจะพัง
  จึงต้องล้มแบบเงียบและปล่อยให้ตู้ทำงานต่อได้เสมอ ไม่ใช่ค้างรอ
"""

from __future__ import annotations

import html
import logging
import re
import threading
import time
from typing import Any

from .. import config

log = logging.getLogger("kiosk.reg")

BASE = "https://reg.mju.ac.th/registrar/"
DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

# ระบบทะเบียนเก่าและส่งหน้าเว็บเป็นรหัสอักขระ TIS-620 ไม่ใช่ UTF-8
_ENCODING = "tis-620"

# กันไม่ให้ตู้ยิงคำขอซ้ำ ๆ ไปที่ระบบทะเบียนของมหาวิทยาลัย
# ผลลัพธ์อยู่ในหน่วยความจำเท่านั้น และหายไปเมื่อปิดเซิร์ฟเวอร์
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()
CACHE_SECONDS = 600.0


class RegError(Exception):
    """ดึงข้อมูลไม่สำเร็จ ผู้เรียกต้องใช้ข้อมูลในเครื่องแทน"""


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or "").replace("\xa0", " "))).strip()


def _parse_grid(page: str) -> list[dict[str, Any]]:
    """อ่านตารางเรียนแบบตารางเวลาออกมาเป็นรายการคาบ

    หนึ่งชั่วโมงในตารางกว้างเท่ากับ COLSPAN 12 ช่อง คือช่องละ 5 นาที
    ตำแหน่งของช่องจึงบอกเวลาเริ่มได้ และความกว้างบอกความยาวของคาบ
    """
    header = re.search(r"Day/Time.*?</TR>", page, re.S)
    if not header:
        return []
    times = re.findall(r"(\d{1,2}):(\d\d)-\d{1,2}:\d\d", header.group(0))
    if not times:
        return []
    base = int(times[0][0]) * 60 + int(times[0][1])

    out: list[dict[str, Any]] = []
    for tr in re.findall(r"<TR BGCOLOR=#F0F0F0>(.*?)</TR>", page[header.end():], re.S):
        cells = re.findall(r"<TD([^>]*)>(.*?)(?=<TD|$)", tr, re.S)
        if not cells:
            continue
        day = _clean(cells[0][1])
        if day not in DAYS:
            continue

        pos = 0
        for attrs, body in cells[1:]:
            m = re.search(r"COLSPAN=(\d+)", attrs, re.I)
            span = int(m.group(1)) if m else 0
            if "class_info_2" in body:
                start, end = base + pos * 5, base + (pos + span) * 5
                code_m = re.search(r"<font face=tahoma>(.*?)</a>", body, re.S | re.I)
                title_m = re.search(r'TITLE="([^"]*)"', body)
                parts = [_clean(x) for x in re.split(r"<BR>", body, flags=re.I)]
                info = parts[1] if len(parts) > 1 else ""
                detail = re.match(r"\((\d+)\)\s*(\d+),\s*(.*)", info)
                out.append({
                    "day": DAYS.index(day) + 1,           # 1 = จันทร์ ให้ตรงกับฐานข้อมูล
                    "start": f"{start // 60:02d}:{start % 60:02d}",
                    "end": f"{end // 60:02d}:{end % 60:02d}",
                    "code": _clean(code_m.group(1)) if code_m else None,
                    "name": title_m.group(1).split(":")[0].strip() if title_m else None,
                    "section": int(detail.group(2)) if detail else None,
                    "room": detail.group(3).strip() if detail else (info or None),
                    "building": parts[2] if len(parts) > 2 else None,
                })
            pos += span
    return out


def _fetch(student_code: str) -> list[dict[str, Any]]:
    import requests

    session = requests.Session()
    session.headers["User-Agent"] = "CSMJU kiosk (student information display)"
    timeout = config.REG_TIMEOUT_SECONDS

    def decode(resp) -> str:
        return resp.content.decode(_ENCODING, errors="replace")

    def encode(data: dict[str, str]) -> dict[str, bytes]:
        return {k: v.encode(_ENCODING) for k, v in data.items()}

    session.get(BASE + "home.asp", timeout=timeout)
    found = decode(session.post(
        BASE + "learn_time.asp",
        data=encode({
            "f_cmd": "1", "f_studentcode": student_code, "f_studentname": "",
            "f_studentsurname": "", "f_studentstatus": "", "f_maxrows": "5",
        }),
        timeout=timeout,
    ))

    link = re.search(r"href=[\"']?(learn_time\.asp\?[^\"'\s>]*studentid[^\"'\s>]*)", found, re.I)
    if not link:
        return []

    url = (BASE + html.unescape(link.group(1))
           + f"&acadyear={config.REG_ACADYEAR}&semester={config.REG_SEMESTER}")
    return _parse_grid(decode(session.get(url, timeout=timeout)))


def student_timetable(student_code: str) -> list[dict[str, Any]]:
    """คาบเรียนของนักศึกษาคนนี้ตามระบบทะเบียน

    คืนรายการว่างถ้าระบบทะเบียนไม่มีข้อมูลของรหัสนี้
    โยน RegError เมื่อติดต่อไม่ได้ เพื่อให้ผู้เรียกแยกได้ว่า
    "ไม่มีตาราง" กับ "ถามไม่ได้" ซึ่งต้องบอกผู้ใช้คนละแบบ
    """
    if not config.REG_LOOKUP_ENABLED:
        raise RegError("ปิดการดึงข้อมูลจากระบบทะเบียนไว้")

    code = (student_code or "").strip()
    if not code.isdigit():
        raise RegError("รหัสนักศึกษาไม่ถูกต้อง")

    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(code)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]["sessions"]

    started = time.perf_counter()
    try:
        sessions = _fetch(code)
    except Exception as exc:  # noqa: BLE001 — ระบบทะเบียนล่มต้องไม่ทำให้ตู้ล่ม
        log.warning("ดึงตารางเรียนจากระบบทะเบียนไม่สำเร็จ: %s", exc)
        raise RegError(str(exc)[:120]) from exc

    log.info("ดึงตารางเรียนของรหัส %s ได้ %d คาบ ใน %d ms",
             code[:4] + "xxxxxx", len(sessions),
             round((time.perf_counter() - started) * 1000))

    with _cache_lock:
        _cache[code] = (now, {"sessions": sessions})
    return sessions


def forget(student_code: str | None = None) -> None:
    """ลบผลที่พักไว้ เรียกตอนผู้ใช้ออกจากระบบ

    ตารางเรียนอยู่ในหน่วยความจำเท่านั้นอยู่แล้ว แต่ลบทันทีที่ผู้ใช้เดินจากไป
    ดีกว่ารอให้หมดอายุเอง เพราะคนถัดไปมายืนที่ตู้เดียวกัน
    """
    with _cache_lock:
        if student_code is None:
            _cache.clear()
        else:
            _cache.pop(student_code.strip(), None)
