"""ชั้นเข้าถึงข้อมูล — คำถามที่มีคำตอบแน่นอนถูกตอบจากที่นี่ทั้งหมด

ทุกฟังก์ชันในไฟล์นี้อ่านจาก SQLite โดยตรง ไม่ผ่าน AI จึงยังทำงานได้
แม้อินเทอร์เน็ตขัดข้อง ซึ่งเป็นข้อกำหนดหลักของโครงงาน
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

from . import thai


# ------------------------------------------------------------
# ข้อมูลสาขาและภาคการศึกษา
# ------------------------------------------------------------
def get_department(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM department WHERE id = 1").fetchone()
    if row is None:
        raise LookupError("ยังไม่ได้นำเข้าข้อมูลสาขา — รัน python -m app.seed ก่อน")
    return {
        "name": row["name"],
        "faculty": row["faculty"],
        "abbr": row["abbr"],
        "officeLocation": row["office_location"],
        "officeHours": row["office_hours"],
        "officePhone": row["office_phone"],
        "officeEmail": row["office_email"],
    }


def get_current_term(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM terms WHERE is_current = 1").fetchone()


def contact_fallback(conn: sqlite3.Connection) -> list[str]:
    """ข้อความติดต่อสาขา ใช้ซ้ำทุกครั้งที่ไม่พบข้อมูล"""
    dept = get_department(conn)
    return [
        dept["officeLocation"],
        dept["officeHours"],
        f"โทร {dept['officePhone']} · อีเมล {dept['officeEmail']}",
    ]


# ------------------------------------------------------------
# ประกาศ และคำถามยอดนิยม
# ------------------------------------------------------------
def list_announcements(conn: sqlite3.Connection, today: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, tag, title, detail FROM announcements
        WHERE active = 1
          AND (starts_on IS NULL OR starts_on <= ?)
          AND (ends_on   IS NULL OR ends_on   >= ?)
        ORDER BY sort_order, id
        """,
        (today, today),
    ).fetchall()
    return [
        {"id": str(r["id"]), "tag": r["tag"], "title": r["title"], "detail": r["detail"]}
        for r in rows
    ]


def list_quick_questions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM quick_questions WHERE active = 1 ORDER BY sort_order, id"
    ).fetchall()
    return [
        {
            "id": r["id"],
            "label": r["label"],
            "kind": r["kind"],
            "source": r["source"],
            "personal": bool(r["personal"]),
        }
        for r in rows
    ]


def get_quick_question(conn: sqlite3.Connection, qid: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM quick_questions WHERE id = ? AND active = 1", (qid,)
    ).fetchone()


# ------------------------------------------------------------
# นักศึกษา
# ------------------------------------------------------------
def mask_student_id(student_id: str) -> str:
    """'6604101001' → '••••1001' — หน้าจอมองเห็นได้จากคนเดินผ่าน
    จึงไม่ส่งรหัสเต็มออกจากเซิร์ฟเวอร์เลย
    """
    return "••••" + student_id[-4:]


def find_student_by_code(conn: sqlite3.Connection, student_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id.strip(),)
    ).fetchone()


def get_student(conn: sqlite3.Connection, pk: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM students WHERE id = ?", (pk,)).fetchone()


def student_public(row: sqlite3.Row, *, restricted: bool = False) -> dict[str, Any]:
    """รูปแบบที่ส่งออกหน้าจอ — ไม่มีรหัสนักศึกษาเต็มอยู่ในนี้

    restricted = True สำหรับโหมดกรอกรหัสนักศึกษา ซึ่งไม่มีการยืนยันตัวตน
    จึงไม่เปิดเผยชื่ออาจารย์ที่ปรึกษา (เป็นข้อมูลที่ใช้เดาตัวบุคคลต่อได้)
    """
    data = {
        "id": row["id"],
        "name": row["name"],
        "studentIdMasked": mask_student_id(row["student_id"]),
        "year": row["year"],
        "program": row["program"],
        "advisor": None if restricted else row["advisor"],
        "restricted": restricted,
    }
    return data


# ------------------------------------------------------------
# ตารางเรียน
# ------------------------------------------------------------
_SCHEDULE_SQL = """
    SELECT s.day, s.start_time, s.end_time, s.teacher,
           c.code, c.name,
           r.code AS room, r.building, r.floor, r.directions
    FROM enrollments e
    JOIN sections s ON s.id = e.section_id
    JOIN courses  c ON c.id = s.course_id
    LEFT JOIN rooms r ON r.id = s.room_id
    WHERE e.student_id = ? AND s.term_id = ?
    ORDER BY s.day, s.start_time
"""


def _section(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "day": row["day"],
        "start": row["start_time"],
        "end": row["end_time"],
        "code": row["code"],
        "name": row["name"],
        "room": row["room"],
        "building": row["building"],
        "floor": row["floor"],
        "teacher": row["teacher"],
        "directions": row["directions"],
    }


def get_schedule(conn: sqlite3.Connection, student_pk: int, term_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(_SCHEDULE_SQL, (student_pk, term_id)).fetchall()
    return [_section(r) for r in rows]


def get_exams(conn: sqlite3.Connection, student_pk: int, term_id: int) -> list[dict[str, Any]]:
    """กำหนดสอบมาจากรายวิชาที่ลงทะเบียน — ไม่ต้องนำเข้าซ้ำรายคน"""
    rows = conn.execute(
        """
        SELECT DISTINCT x.exam_type, x.exam_date, x.start_time, x.end_time,
               c.code, c.name, r.code AS room
        FROM enrollments e
        JOIN sections s ON s.id = e.section_id
        JOIN exams    x ON x.course_id = s.course_id AND x.term_id = s.term_id
        JOIN courses  c ON c.id = x.course_id
        LEFT JOIN rooms r ON r.id = x.room_id
        WHERE e.student_id = ? AND s.term_id = ?
        ORDER BY x.exam_date, x.start_time
        """,
        (student_pk, term_id),
    ).fetchall()

    exams = []
    for r in rows:
        exam_date = datetime.strptime(r["exam_date"], "%Y-%m-%d").date()
        exams.append(
            {
                "code": r["code"],
                "name": r["name"],
                "type": r["exam_type"],
                "dateISO": r["exam_date"],
                "dateLabel": f"{thai.weekday_name(exam_date)} {thai.format_date(exam_date)}",
                "time": f"{r['start_time']}–{r['end_time']}",
                "room": r["room"],
            }
        )
    return exams


def classes_today(schedule: list[dict[str, Any]], at: datetime) -> list[dict[str, Any]]:
    return [s for s in schedule if s["day"] == at.isoweekday()]


def classes_by_week(schedule: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """จัดกลุ่มจันทร์–ศุกร์ วันที่ไม่มีเรียนคืนลิสต์ว่าง"""
    return {day: [s for s in schedule if s["day"] == day] for day in range(1, 6)}


def find_next_class(
    schedule: list[dict[str, Any]], at: datetime
) -> dict[str, Any] | None:
    """หาคาบถัดไป มองไปข้างหน้าได้สูงสุด 8 วัน

    ถ้ากำลังเรียนอยู่จะคืนคาบปัจจุบันพร้อม ongoing = True
    ถ้าวันนี้เลิกเรียนแล้วจะข้ามไปคาบแรกของวันเรียนถัดไปโดยอัตโนมัติ
    """
    if not schedule:
        return None

    for offset in range(8):
        day = (at + timedelta(days=offset)).date()
        items = sorted(
            (s for s in schedule if s["day"] == day.isoweekday()),
            key=lambda s: s["start"],
        )
        for item in items:
            start = thai.at_time(day, item["start"])
            end = thai.at_time(day, item["end"])
            if at < end:
                return {
                    "item": item,
                    "startISO": start.isoformat(),
                    "endISO": end.isoformat(),
                    "dayOffset": offset,
                    "dayLabel": thai.relative_day_label(offset, day),
                    "ongoing": at >= start,
                    "isToday": offset == 0,
                    "countdown": thai.format_countdown(start - at),
                }
    return None


# ------------------------------------------------------------
# สถานะข้อมูลใบหน้า
# ------------------------------------------------------------
def face_status(conn: sqlite3.Connection, student_pk: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT f.created_at, f.model, COUNT(*) OVER () AS total
        FROM face_embeddings f
        JOIN consents c ON c.id = f.consent_id AND c.revoked_at IS NULL
        WHERE f.student_id = ?
        ORDER BY f.created_at
        LIMIT 1
        """,
        (student_pk,),
    ).fetchone()

    if row is None:
        return {"enrolled": False, "enrolledAtLabel": None, "vectorCount": 0}

    enrolled_at = datetime.fromisoformat(row["created_at"])
    return {
        "enrolled": True,
        "enrolledAtLabel": thai.format_date(enrolled_at.date()),
        "vectorCount": row["total"],
        "model": row["model"],
    }


# ------------------------------------------------------------
# สถิติการใช้งาน (ไม่มีข้อมูลระบุตัวตน)
# ------------------------------------------------------------
def log_usage(
    conn: sqlite3.Connection,
    *,
    question_kind: str | None,
    channel: str | None,
    answer_source: str | None,
    latency_ms: int | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO usage_events (occurred_at, question_kind, channel, answer_source, latency_ms)
        VALUES (?, ?, ?, ?, ?)
        """,
        (thai.now().isoformat(timespec="seconds"), question_kind, channel, answer_source, latency_ms),
    )
    conn.commit()
