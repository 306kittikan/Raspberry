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
        "website": row["website"],
        "officeLocation": row["office_location"],
        # เวลาทำการไม่มีในข้อมูลจริง จึงเป็น None ได้ หน้าจอต้องรับมือได้
        "officeHours": row["office_hours"],
        "officePhone": row["office_phone"],
        "officeEmail": row["office_email"],
    }


def list_contacts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT type, title, value, label FROM contacts ORDER BY sort_order, id"
    ).fetchall()
    return [
        {"type": r["type"], "title": r["title"], "value": r["value"], "label": r["label"]}
        for r in rows
    ]


def has_synthetic_schedule(conn: sqlite3.Connection) -> bool:
    """ตารางเรียนที่อยู่ในระบบยังเป็นข้อมูลสมมติหรือไม่

    ใช้ขึ้นป้ายเตือนบนหน้าจอ เพื่อไม่ให้ใครเข้าใจผิดว่าเป็นตารางเรียนจริง
    """
    row = conn.execute("SELECT 1 FROM sections WHERE is_synthetic = 1 LIMIT 1").fetchone()
    return row is not None


def get_current_term(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM terms WHERE is_current = 1").fetchone()


def contact_fallback(conn: sqlite3.Connection) -> list[str]:
    """ข้อความติดต่อสาขา ใช้ซ้ำทุกครั้งที่ไม่พบข้อมูล

    ประกอบจากช่องทางที่มีจริงเท่านั้น ช่องไหนไม่มีข้อมูลก็ไม่แสดง
    """
    dept = get_department(conn)
    lines: list[str] = []
    if dept["officeLocation"]:
        lines.append(f"สำนักงานสาขาวิชาฯ {dept['officeLocation']}")
    if dept["officeHours"]:
        lines.append(dept["officeHours"])

    channels = []
    if dept["officePhone"]:
        channels.append(f"โทร {dept['officePhone']}")
    if dept["officeEmail"]:
        channels.append(f"อีเมล {dept['officeEmail']}")
    if channels:
        lines.append(" · ".join(channels))
    return lines


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
    SELECT s.day, s.start_time, s.end_time, s.teacher, s.is_synthetic,
           c.code, c.name,
           r.name AS room_name, r.short_name AS room_short, r.room_type,
           r.floor, r.directions, b.name AS building
    FROM enrollments e
    JOIN sections s ON s.id = e.section_id
    JOIN courses  c ON c.id = s.course_id
    LEFT JOIN rooms     r ON r.id = s.room_id
    LEFT JOIN buildings b ON b.id = r.building_id
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
        # ชื่อย่อ ('Lab 3') อ่านจากระยะยืนได้ดีกว่าชื่อเต็ม จึงใช้เป็นหลัก
        "room": row["room_short"] or row["room_name"],
        "roomFullName": row["room_name"],
        "roomType": row["room_type"],
        "building": row["building"],
        "floor": row["floor"],
        "teacher": row["teacher"],
        "directions": row["directions"],
        "isSynthetic": bool(row["is_synthetic"]),
    }


def get_schedule(conn: sqlite3.Connection, student_pk: int, term_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(_SCHEDULE_SQL, (student_pk, term_id)).fetchall()
    return [_section(r) for r in rows]


def get_exams(conn: sqlite3.Connection, student_pk: int, term_id: int) -> list[dict[str, Any]]:
    """กำหนดสอบมาจากรายวิชาที่ลงทะเบียน — ไม่ต้องนำเข้าซ้ำรายคน"""
    rows = conn.execute(
        """
        SELECT DISTINCT x.exam_type, x.exam_date, x.start_time, x.end_time,
               c.code, c.name, COALESCE(r.short_name, r.name) AS room
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
# บุคลากร
# ------------------------------------------------------------
def list_public_personnel(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """เฉพาะบุคลากรที่ระบบต้นทางกำหนดให้เปิดเผยข้อมูลได้

    ตู้ตั้งในที่สาธารณะและคนเดินผ่านมองเห็นจอ จึงไม่แสดงคนที่ปิดโปรไฟล์ไว้
    """
    rows = conn.execute(
        """
        SELECT prefix, fullname_th, academic_position, administrative_position,
               email, phone, expertise
        FROM personnel
        WHERE is_public = 1 AND email IS NOT NULL
        ORDER BY
          CASE WHEN administrative_position IS NOT NULL THEN 0 ELSE 1 END,
          fullname_th
        """
    ).fetchall()
    return [
        {
            "name": f"{r['prefix'] or ''}{r['fullname_th']}".strip(),
            "position": r["administrative_position"] or r["academic_position"],
            "email": r["email"],
            "phone": r["phone"],
            "expertise": r["expertise"],
        }
        for r in rows
    ]


def find_teacher(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    """หาผู้สอนจากชื่อที่ปรากฏในตารางเรียน"""
    if not name:
        return None
    for person in list_public_personnel(conn):
        # ชื่อในตารางเรียนอาจมีคำนำหน้าไม่ตรงกันทุกตัวอักษร จึงเทียบด้วยการเป็นส่วนหนึ่งของกัน
        bare = name.replace("ผศ.", "").replace("ดร.", "").replace("อ.", "").strip()
        if bare and bare in person["name"]:
            return person
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
