"""ตัวแปลคำถาม → คำตอบ พร้อมระบุแหล่งที่มาเสมอ

กติกาที่ห้ามผิดพลาด:
  db   = ตารางเรียน ห้องเรียน กำหนดสอบ → ค้น SQLite โดยตรง ไม่ผ่าน AI
         จึงไม่มีโอกาสตอบผิด และยังตอบได้ขณะอินเทอร์เน็ตขัดข้อง
  ai   = คำถามทั่วไป → ส่งให้ผู้ช่วย AI ซึ่งต้องอ้างอิงเอกสารเสมอ
  none = ไม่พบข้อมูลในระบบ → ห้ามเดาคำตอบ ให้บอกช่องทางติดต่อสาขาแทน

รูปแบบคำตอบตรงกับที่ web/src/components/AnswerCard.jsx ใช้แสดงผล
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from . import repo, thai


@dataclass(slots=True)
class AskContext:
    """สภาพแวดล้อมของคำถามหนึ่งครั้ง"""

    student_pk: int | None
    term_id: int | None
    online: bool = True
    restricted: bool = False  # โหมดกรอกรหัสนักศึกษา ไม่มีการยืนยันตัวตน


UNCLEAR_ANSWER: dict[str, Any] = {
    "source": "none",
    "unclear": True,
    "title": "ขออภัย ไม่ได้ยินชัดเจน",
    "lines": ["ลองพูดอีกครั้งหรือแตะเลือกคำถามด้านล่าง"],
}


def _base(q: sqlite3.Row) -> dict[str, Any]:
    return {"questionId": q["id"], "kind": q["kind"], "label": q["label"]}


def _no_schedule(conn: sqlite3.Connection, base: dict[str, Any]) -> dict[str, Any]:
    return {
        **base,
        "source": "db",
        "title": "ยังไม่มีข้อมูลตารางเรียน",
        "lines": [
            "ยังไม่มีข้อมูลตารางเรียนภาคการศึกษานี้ กรุณาติดต่อสำนักงานสาขา",
            *repo.contact_fallback(conn),
        ],
    }


def _not_found(conn: sqlite3.Connection, base: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        **base,
        "source": "none",
        "title": "ไม่พบข้อมูลนี้ในระบบ",
        "lines": [reason, *repo.contact_fallback(conn)],
    }


def _room_lines(item: dict[str, Any]) -> list[str]:
    """บรรยายตำแหน่งห้องจากข้อมูลที่มีจริงเท่านั้น

    ถ้าฐานข้อมูลไม่มีคำแนะนำการเดินทางของห้องนั้น จะไม่แต่งขึ้นมาเอง
    """
    lines = [f"อยู่ชั้น {item['floor']} {item['building']}"]
    lines.append(
        f"ใช้เรียนวิชา {item['name']} เวลา {item['start']}–{item['end']} น."
    )
    if item.get("directions"):
        lines.append(item["directions"])
    return lines


# ------------------------------------------------------------
# คำตอบที่มาจากฐานข้อมูลโดยตรง
# ------------------------------------------------------------
def _answer_from_db(
    conn: sqlite3.Connection, q: sqlite3.Row, ctx: AskContext
) -> dict[str, Any]:
    base = _base(q)
    now = thai.now()

    if q["id"] in {"next-class", "room-floor", "exam-subject"}:
        schedule = repo.get_schedule(conn, ctx.student_pk, ctx.term_id)
        if not schedule:
            return _no_schedule(conn, base)

    if q["id"] == "next-class":
        nxt = repo.find_next_class(schedule, now)
        if nxt is None:
            return _no_schedule(conn, base)
        item = nxt["item"]
        return {
            **base,
            "source": "db",
            "title": "คาบที่กำลังเรียนอยู่" if nxt["ongoing"] else "คาบเรียนถัดไปของคุณ",
            "lines": [
                f"{item['code']} {item['name']}",
                f"เวลา {item['start']}–{item['end']} น.",
                f"ห้อง {item['room']} · {item['building']} ชั้น {item['floor']}",
            ],
        }

    if q["id"] == "room-floor":
        nxt = repo.find_next_class(schedule, now)
        if nxt is None:
            return _no_schedule(conn, base)
        item = nxt["item"]
        return {
            **base,
            "source": "db",
            "title": f"ห้อง {item['room']}",
            "lines": _room_lines(item),
        }

    if q["id"] == "exam-subject":
        exams = repo.get_exams(conn, ctx.student_pk, ctx.term_id)
        today = now.date().isoformat()
        upcoming = [e for e in exams if e["dateISO"] >= today]
        if not upcoming:
            return {
                **base,
                "source": "db",
                "title": "ไม่มีกำหนดสอบที่จะถึง",
                "lines": (
                    ["กำหนดสอบของภาคการศึกษานี้ผ่านไปหมดแล้ว"]
                    if exams
                    else ["ยังไม่มีประกาศกำหนดสอบในภาคการศึกษานี้"]
                )
                + ["ติดตามประกาศจากสำนักงานสาขาวิชาฯ อีกครั้ง"],
            }
        exam = upcoming[0]
        return {
            **base,
            "source": "db",
            "title": f"{exam['type']}วิชา {exam['name']}",
            "lines": [
                f"{exam['dateLabel']} เวลา {exam['time']} น.",
                f"ห้องสอบ {exam['room']}",
                'ดูกำหนดสอบทั้งหมดได้ที่แท็บ "กำหนดสอบ" บนหน้าหลัก',
            ],
        }

    dept = repo.get_department(conn)

    if q["id"] == "contact-teacher":
        return {
            **base,
            "source": "db",
            "title": "ติดต่ออาจารย์ประจำสาขาวิชาฯ",
            "lines": [
                f"ห้องพักอาจารย์ {dept['officeLocation']}",
                f"เวลาราชการ {dept['officeHours']}",
                f"นัดหมายล่วงหน้าได้ที่ {dept['officePhone']} หรือ {dept['officeEmail']}",
            ],
        }

    if q["id"] == "office-hours":
        return {
            **base,
            "source": "db",
            "title": f"สำนักงาน{dept['name']}",
            "lines": [
                dept["officeLocation"],
                f"เปิดทำการ {dept['officeHours']}",
                f"โทร {dept['officePhone']}",
            ],
        }

    return _not_found(conn, base, "ระบบไม่พบข้อมูลสำหรับคำถามนี้")


# ------------------------------------------------------------
# ทางเข้าหลัก
# ------------------------------------------------------------
async def resolve(
    conn: sqlite3.Connection, question_id: str, ctx: AskContext
) -> dict[str, Any]:
    q = repo.get_quick_question(conn, question_id)
    if q is None:
        return {
            "questionId": question_id,
            "kind": None,
            "label": None,
            "source": "none",
            "title": "ไม่รู้จักคำถามนี้",
            "lines": ["กรุณาเลือกจากคำถามยอดนิยมด้านล่าง"],
        }

    base = _base(q)

    # ---- คำถามที่ต้องยืนยันตัวตนก่อน ----
    if q["personal"] and ctx.student_pk is None:
        return {
            **base,
            "source": "none",
            "title": "ต้องยืนยันตัวตนก่อน",
            "lines": [
                "คำถามนี้ต้องใช้ตารางเรียนส่วนบุคคล",
                "กรุณายืนยันตัวตนด้วยใบหน้า หรือกรอกรหัสนักศึกษาที่หน้าจอพัก",
            ],
            "needAuth": True,
        }

    if q["source"] == "db":
        return _answer_from_db(conn, q, ctx)

    if q["source"] == "none":
        return _not_found(
            conn, base, "ระบบไม่พบเอกสารอ้างอิงสำหรับคำถามนี้ จึงไม่สามารถตอบได้"
        )

    # ---- ผู้ช่วย AI ----
    if not ctx.online:
        return {
            **base,
            "source": "none",
            "title": "ผู้ช่วย AI ไม่พร้อมใช้งานขณะออฟไลน์",
            "lines": [
                "ขณะนี้ตู้ไม่ได้เชื่อมต่ออินเทอร์เน็ต จึงตอบคำถามที่ต้องใช้ผู้ช่วย AI ไม่ได้",
                "ตารางเรียนและกำหนดสอบยังใช้งานได้ตามปกติ",
            ],
            "offlineBlocked": True,
        }

    from .services import assistant_ai  # นำเข้าตรงนี้เพื่อไม่บังคับติดตั้ง SDK ตอนออฟไลน์

    return await assistant_ai.answer(conn, base, q["label"])


def today_iso() -> str:
    return date.fromisoformat(thai.now().date().isoformat()).isoformat()
