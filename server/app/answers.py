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
    text: str = ""            # ข้อความที่ผู้ใช้ถามมาจริง ใช้หาชื่อบุคคลที่เอ่ยถึง


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


def _where(item: dict[str, Any]) -> str:
    """'ห้อง Lab 3 · ตึก 60 ปี คณะวิทยาศาสตร์ ชั้น 6' — ข้ามส่วนที่ไม่มีข้อมูล"""
    parts = []
    if item.get("room"):
        parts.append(f"ห้อง {item['room']}")
    place = []
    if item.get("building"):
        place.append(item["building"])
    if item.get("floor") is not None:
        place.append(f"ชั้น {item['floor']}")
    if place:
        parts.append(" ".join(place))
    return " · ".join(parts) if parts else "ยังไม่ระบุห้องเรียน"


def _room_lines(item: dict[str, Any]) -> list[str]:
    """บรรยายตำแหน่งห้องจากข้อมูลที่มีจริงเท่านั้น

    ช่องไหนว่างก็ไม่พูดถึง และถ้าฐานข้อมูลไม่มีคำแนะนำการเดินทางของห้องนั้น
    จะไม่แต่งขึ้นมาเอง เพราะพาคนเดินผิดตึกแย่กว่าไม่บอก
    """
    lines: list[str] = []
    place = []
    if item.get("floor") is not None:
        place.append(f"อยู่ชั้น {item['floor']}")
    if item.get("building"):
        place.append(item["building"])
    if place:
        lines.append(" ".join(place))

    if item.get("roomFullName"):
        lines.append(item["roomFullName"])

    lines.append(f"ใช้เรียนวิชา {item['name']} เวลา {item['start']}–{item['end']} น.")
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
                _where(item),
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
            "title": f"ห้อง {item['room']}" if item.get("room") else "ยังไม่ระบุห้องเรียน",
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
        # ถ้ายืนยันตัวตนแล้วและมีคาบเรียน ให้ตอบผู้สอนของคาบถัดไปก่อน
        # เพราะเป็นคนที่นักศึกษาน่าจะกำลังตามหาที่สุด
        if ctx.student_pk is not None:
            schedule = repo.get_schedule(conn, ctx.student_pk, ctx.term_id)
            nxt = repo.find_next_class(schedule, now)
            teacher = repo.find_teacher(conn, nxt["item"]["teacher"]) if nxt else None
            if teacher:
                lines = [f"{teacher['name']}"]
                if teacher["position"]:
                    lines.append(teacher["position"])
                if teacher["email"]:
                    lines.append(f"อีเมล {teacher['email']}")
                if teacher["phone"]:
                    lines.append(f"โทร {teacher['phone']}")
                return {
                    **base,
                    "source": "db",
                    "title": f"ผู้สอนวิชา {nxt['item']['name']}",
                    "lines": lines,
                }

        staff = repo.list_public_personnel(conn)
        if not staff:
            return _not_found(conn, base, "ยังไม่มีข้อมูลบุคลากรในระบบ")
        return {
            **base,
            "source": "db",
            "title": "ติดต่ออาจารย์ประจำสาขาวิชาฯ",
            "lines": [
                *[f"{p['name']} · {p['email']}" for p in staff[:3]],
                f"ดูรายชื่อทั้งหมดได้ที่สำนักงานสาขาวิชาฯ หรือ {dept['officeEmail']}",
            ],
        }

    if q["id"] == "office-contact":
        # เวลาทำการไม่มีในข้อมูลของสาขา จึงไม่ตอบเรื่องเวลา
        # ตอบเฉพาะที่ตั้งและช่องทางติดต่อซึ่งเป็นข้อมูลจริง
        lines = []
        if dept["officeLocation"]:
            lines.append(dept["officeLocation"])
        if dept["officeHours"]:
            lines.append(f"เปิดทำการ {dept['officeHours']}")
        for c in repo.list_contacts(conn):
            if c["type"] in {"phone", "email"}:
                lines.append(f"{c['title']} {c['value']}")
        if not lines:
            return _not_found(conn, base, "ยังไม่มีข้อมูลการติดต่อสำนักงานในระบบ")
        return {
            **base,
            "source": "db",
            "title": f"สำนักงาน{dept['name']}",
            "lines": lines[:4],
        }

    return _not_found(conn, base, "ระบบไม่พบข้อมูลสำหรับคำถามนี้")


# ------------------------------------------------------------
# ทางเข้าหลัก
# ------------------------------------------------------------
async def resolve(
    conn: sqlite3.Connection, question_id: str, ctx: AskContext
) -> dict[str, Any]:
    # คำถามที่เอ่ยชื่อบุคลากร ตอบจากตารางบุคลากรโดยตรง
    # ไม่ได้มาจากปุ่มคำถามยอดนิยม จึงไม่มีแถวใน quick_questions
    if question_id == "person-detail":
        person = repo.find_personnel_mention(conn, ctx.text)
        if person is not None:
            return {
                "questionId": "person-detail",
                "kind": "บุคลากร",
                "label": ctx.text,
                "source": "db",
                "title": person["name"],
                "lines": repo.personnel_lines(person),
            }

    if question_id == "today-datetime":
        now = thai.now()
        return {
            "questionId": "today-datetime",
            "kind": "วันเวลา",
            "label": ctx.text,
            "source": "db",
            "title": "วันและเวลาขณะนี้",
            "lines": [
                f"วัน{thai.weekday_name(now.date())}ที่ {thai.format_date(now.date())}",
                f"เวลา {now.hour:02d}.{now.minute:02d} น.",
            ],
        }

    if question_id == "exam-public":
        rows = repo.search_exam_schedule(conn, ctx.text)
        if rows:
            return {
                "questionId": "exam-public",
                "kind": "กำหนดสอบ",
                "label": ctx.text,
                "source": "db",
                "title": rows[0]["exam_label"] or "ตารางสอบ",
                "lines": repo.exam_lines(rows),
                "ref": "สำนักบริหารและพัฒนาวิชาการ · ตารางสอบ",
            }

    if question_id == "academic-calendar":
        rows = repo.upcoming_calendar(conn, today_iso())
        if rows:
            return {
                "questionId": "academic-calendar",
                "kind": "ปฏิทินการศึกษา",
                "label": ctx.text,
                "source": "db",
                "title": "ปฏิทินการศึกษาที่กำลังจะถึง",
                "lines": repo.calendar_lines(rows),
                "ref": "สำนักบริหารและพัฒนาวิชาการ · ปฏิทินการศึกษา",
            }

    if question_id == "edu-forms":
        rows = repo.search_forms(conn, ctx.text)
        if rows:
            return {
                "questionId": "edu-forms",
                "kind": "เอกสารและแบบฟอร์ม",
                "label": ctx.text,
                "source": "db",
                "title": "เอกสารที่เกี่ยวข้อง",
                "lines": [r["title"] for r in rows],
                "links": [{"title": r["title"], "url": r["url"]} for r in rows],
                "ref": "สำนักบริหารและพัฒนาวิชาการ · เอกสารและแบบฟอร์ม",
            }

    if question_id == "person-topic":
        people = repo.search_personnel_by_topic(conn, ctx.text)
        if people:
            topics = sorted({t for p in people for t in p["topics"]})
            lines = [f"{p['name']} · {p['email']}" for p in people]
            return {
                "questionId": "person-topic",
                "kind": "บุคลากร",
                "label": ctx.text,
                "source": "db",
                "title": f"อาจารย์ที่เชี่ยวชาญด้าน {', '.join(topics)}",
                "lines": lines,
            }

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
