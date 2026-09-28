"""อ่านคำตอบออกเสียงเป็นภาษาไทย

ใช้ Piper กับเสียง th_TH-tsync2 ซึ่งทำงานบนเครื่องล้วน ๆ ไม่ต้องต่อเน็ต
เลือกแบบทำงานบนเครื่องเพราะตู้ต้องพูดได้แม้เครือข่ายล่ม
และเพราะข้อความที่พูดคือคำถามของนักศึกษา ซึ่งไม่ควรถูกส่งออกไปข้างนอก

ส่วนที่สำคัญที่สุดของไฟล์นี้ไม่ใช่การสังเคราะห์เสียง แต่เป็น speakable()
ตัวแยกเสียงภาษาไทยจะ "ทิ้ง" อักษรอังกฤษและตัวเลขที่ปนอยู่ในประโยคไปเฉย ๆ
คำตอบของตู้เต็มไปด้วยรหัสวิชา เวลา และชื่อห้องอย่าง Lab คอม3-4
ถ้าปล่อยไปตรง ๆ ตู้จะพูดข้อมูลผิดโดยที่ข้อความบนจอถูก ซึ่งอันตรายกว่าไม่พูดเลย
"""

from __future__ import annotations

import hashlib
import io
import re
import threading
import wave
from collections import OrderedDict
from typing import Any

from .. import config

# ---- เตรียมข้อความให้อ่านออกเสียงได้ถูกต้อง ----

_THAI_DIGITS = ("ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า")

# คำอังกฤษที่โผล่ในคำตอบของตู้บ่อย ๆ เขียนคำอ่านไทยกำกับไว้
# ไม่ได้ครอบคลุมทุกคำ แต่ครอบคลุมคำที่ตู้พูดจริงเกือบทั้งหมด
_ENGLISH_READINGS: dict[str, str] = {
    "lab": "แล็บ",
    "com": "คอม",
    "computer": "คอมพิวเตอร์",
    "wifi": "วายฟาย",
    "wi-fi": "วายฟาย",
    "it": "ไอที",
    "iot": "ไอโอที",
    "ai": "เอไอ",
    "cs": "ซีเอส",
    "mju": "เอ็มเจยู",
    "email": "อีเมล",
    "e-mail": "อีเมล",
    "sec": "เซค",
    "section": "เซคชัน",
    "qr": "คิวอาร์",
    "gpa": "จีพีเอ",
    "gpax": "จีแพ็ก",
    "python": "ไพทอน",
    "java": "จาวา",
    "web": "เว็บ",
    "data": "ดาต้า",
    "network": "เน็ตเวิร์ก",
}

# อีเมลและเว็บไซต์ อ่านออกเสียงแล้วไม่มีใครจดทัน และฟังเป็นขยะ
# บอกให้ดูบนจอแทน ข้อความเต็มอยู่ตรงนั้นอยู่แล้ว
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"https?://\S+|www\.\S+")

# เวลาแบบ 15:00 หรือ 09:30
_TIME = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
# ช่วงเวลาแบบ 13:00-15:00
_TIME_RANGE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s*[-–]\s*([01]?\d|2[0-3]):([0-5]\d)\b")
# รหัสวิชา 8 หลัก
_COURSE_CODE = re.compile(r"\b(\d{8})\b")
# คำอังกฤษ
_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z\-]*")
# ตัวเลขที่เหลือ
_NUMBER = re.compile(r"\d+")
# จุดนำหน้ารายการและอักขระประดับที่ไม่ควรอ่าน
_BULLET = re.compile(r"[·•●▪]")


def _digits_thai(digits: str) -> str:
    """อ่านตัวเลขทีละตัว ใช้กับรหัสวิชาและเลขห้อง

    รหัสวิชา 10301222 ต้องอ่านว่า หนึ่ง-ศูนย์-สาม-... ไม่ใช่ สิบล้านสามแสน...
    เพราะนักศึกษาจดตามทีละหลัก
    """
    return " ".join(_THAI_DIGITS[int(d)] for d in digits if d.isdigit())


def _read_number(n: int) -> str:
    """อ่านจำนวนเต็มเป็นคำไทย ใช้กับเลขจำนวนน้อย ๆ อย่างชั้นและหน่วยกิต"""
    if n < 10:
        return _THAI_DIGITS[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        head = "" if tens == 1 else ("ยี่" if tens == 2 else _THAI_DIGITS[tens])
        tail = "" if ones == 0 else ("เอ็ด" if ones == 1 and tens > 0 else _THAI_DIGITS[ones])
        return f"{head}สิบ{tail}"
    return _digits_thai(str(n))


def _read_time(hh: str, mm: str) -> str:
    h, m = int(hh), int(mm)
    if m == 0:
        return f"{_read_number(h)}นาฬิกา"
    if m == 30:
        return f"{_read_number(h)}นาฬิกาครึ่ง"
    return f"{_read_number(h)}นาฬิกา{_read_number(m)}นาที"


def speakable(text: str) -> str:
    """แปลงคำตอบบนจอให้เป็นข้อความที่อ่านออกเสียงแล้วได้ความหมายเดิม

    ทำงานเรียงจากรูปแบบที่เจาะจงที่สุดไปกว้างที่สุด
    ถ้าสลับลำดับ เวลา 15:00 จะถูกตัวจับตัวเลขทั่วไปกินไปก่อน
    """
    if not text:
        return ""

    s = _BULLET.sub(" ", text)

    # ตัดที่อยู่อีเมลกับลิงก์ออกก่อนทุกอย่าง ไม่งั้นจะถูกกฎอื่นสับเป็นชิ้น ๆ
    s = _EMAIL.sub("ตามที่แสดงบนหน้าจอ", s)
    s = _URL.sub("ตามที่แสดงบนหน้าจอ", s)

    # ช่วงเวลาต้องมาก่อนเวลาเดี่ยว ไม่งั้นจะได้ "ถึง" หายไป
    s = _TIME_RANGE.sub(
        lambda m: f"{_read_time(m[1], m[2])} ถึง {_read_time(m[3], m[4])}", s
    )
    s = _TIME.sub(lambda m: _read_time(m[1], m[2]), s)
    # "15:00 น." กลายเป็น "สิบห้านาฬิกา น." ซึ่งพูดซ้ำความหมายเดิม
    s = re.sub(r"(นาฬิกา(?:ครึ่ง)?(?:[^ ]*นาที)?)\s*น\.", r"\1", s)
    s = _COURSE_CODE.sub(lambda m: f"รหัสวิชา {_digits_thai(m[1])}", s)

    def _latin(m: re.Match[str]) -> str:
        word = m.group()
        return _ENGLISH_READINGS.get(word.lower(), word)

    s = _LATIN_WORD.sub(_latin, s)

    # ตัวเลขที่เหลือ เช่น เลขห้องหรือชั้น อ่านทีละตัวเพื่อความปลอดภัย
    # อ่านผิดเป็นจำนวนทำให้เลขห้องเพี้ยน ซึ่งพาคนเดินผิดชั้น
    s = _NUMBER.sub(lambda m: _digits_thai(m.group()), s)

    # ตัวอักษรอังกฤษที่ไม่มีคำอ่านกำกับ ตัวแยกเสียงจะทิ้งไปอยู่ดี
    # ตัดทิ้งเองพร้อมเว้นวรรคแทน จะได้ไม่เกิดคำติดกันแปลก ๆ
    s = re.sub(r"[A-Za-z]+", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


# ---- สังเคราะห์เสียง ----

_lock = threading.Lock()
_voice: Any | None = None
_load_error: str | None = None

# คำตอบของตู้ซ้ำกันมาก การสังเคราะห์ใหม่ทุกครั้งเปลืองเวลาโดยเปล่าประโยชน์
# บนราสเบอร์รีพายการสังเคราะห์ช้ากว่าเครื่องพัฒนาหลายเท่า แคชจึงสำคัญกว่าเดิม
_CACHE_MAX = 64
_cache: OrderedDict[str, bytes] = OrderedDict()


def available() -> bool:
    return config.TTS_ENABLED and config.TTS_MODEL_PATH.exists()


def _load() -> Any:
    global _voice, _load_error
    if _voice is not None:
        return _voice
    if _load_error is not None:
        raise RuntimeError(_load_error)
    try:
        from piper import PiperVoice

        _voice = PiperVoice.load(str(config.TTS_MODEL_PATH))
        return _voice
    except Exception as exc:  # pragma: no cover - ขึ้นกับเครื่องที่ติดตั้ง
        _load_error = f"โหลดเสียงพูดไม่สำเร็จ: {exc}"
        raise RuntimeError(_load_error) from exc


def synthesize(text: str) -> bytes:
    """คืนไฟล์เสียง WAV ของข้อความนี้ ว่างเปล่าถ้าไม่มีอะไรให้พูด"""
    prepared = speakable(text)
    if not prepared:
        return b""

    key = hashlib.sha256(prepared.encode("utf-8")).hexdigest()
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return hit

    voice = _load()
    buf = io.BytesIO()
    # Piper ไม่ปลอดภัยต่อการเรียกพร้อมกันหลายเธรด จึงล็อกตลอดการสังเคราะห์
    with _lock:
        with wave.open(buf, "wb") as wav:
            voice.synthesize_wav(prepared, wav)
        data = buf.getvalue()
        _cache[key] = data
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return data


def status() -> dict[str, Any]:
    return {
        "enabled": config.TTS_ENABLED,
        "ready": available() and _load_error is None,
        "voice": config.TTS_MODEL_PATH.stem if available() else None,
        "error": _load_error or (None if available() else "ยังไม่ได้ติดตั้งไฟล์เสียง"),
        "cached": len(_cache),
    }
