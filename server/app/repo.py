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


def is_active(student: sqlite3.Row | None) -> bool:
    """ยังเป็นนักศึกษาของสาขาอยู่หรือไม่

    ผู้ที่ลาออกหรือพ้นสภาพไม่ควรเห็นตารางเรียนของภาคการศึกษาปัจจุบัน
    และไม่ควรลงทะเบียนใบหน้าใหม่ได้
    ฐานข้อมูลเก่าที่ยังไม่มีคอลัมน์นี้ถือว่ายังศึกษาอยู่ เพื่อไม่ให้ตู้หยุดทำงาน
    """
    if student is None:
        return False
    if "active" not in student.keys():
        return True
    return bool(student["active"])


def status_message(student: sqlite3.Row) -> str:
    """ข้อความอธิบายสาเหตุที่ใช้ตู้ไม่ได้ ใช้แสดงบนหน้าจอ"""
    label = None
    if "status_label" in student.keys():
        label = student["status_label"]
    reason = f" ({label})" if label else ""
    return (
        f"รหัสนักศึกษานี้ไม่ได้อยู่ในสถานะกำลังศึกษา{reason} "
        "กรุณาติดต่อสำนักงานสาขาวิชาฯ"
    )


def get_student(conn: sqlite3.Connection, pk: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM students WHERE id = ?", (pk,)).fetchone()


def student_public(row: sqlite3.Row, *, restricted: bool = False) -> dict[str, Any]:
    """รูปแบบที่ส่งออกหน้าจอ — ไม่มีรหัสนักศึกษาเต็มอยู่ในนี้

    restricted = True สำหรับโหมดกรอกรหัสนักศึกษา ซึ่งไม่มีการยืนยันตัวตน
    จึงไม่เปิดเผยชื่ออาจารย์ที่ปรึกษา (เป็นข้อมูลที่ใช้เดาตัวบุคคลต่อได้)
    """
    keys = row.keys()
    return {
        "id": row["id"],
        "prefix": row["prefix"] if "prefix" in keys else None,
        "name": row["name"],
        "studentIdMasked": mask_student_id(row["student_id"]),
        "year": row["year"],
        "program": row["program"],
        "advisor": None if restricted else row["advisor"],
        "restricted": restricted,
    }


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


# คำที่บอกว่าผู้ถามกำลังพูดถึง "คน" ไม่ใช่คำพ้องเสียงอย่างอื่น
# จำเป็นเพราะชื่อจริงภาษาไทยบางชื่อสั้นและพ้องกับคำทั่วไป
# เช่น "สนิท" ที่แปลว่าใกล้ชิดได้ด้วย ถ้าจับแค่ชื่อจะเจอผิดใน "เพื่อนสนิท"
_PERSON_WORDS = ("อาจารย์", "อ.", "ผศ.", "รศ.", "ศ.", "ดร.", "ผู้สอน",
                 "ที่ปรึกษา", "คุณ", "เจ้าหน้าที่")


def find_personnel_mention(
    conn: sqlite3.Connection, text: str
) -> dict[str, Any] | None:
    """หาบุคลากรที่ถูกเอ่ยชื่อในคำถาม คืน None ถ้าไม่ได้เจาะจงถึงใคร

    ใช้ตัดสินว่าคำถามนี้ตอบจากฐานข้อมูลได้เลยหรือไม่
    "อีเมลอาจารย์พาสน์คืออะไร" มีคำตอบที่แน่นอนอยู่ในตาราง จึงไม่ควรให้ AI เดา
    ต่างจาก "อาจารย์คนไหนสอนเรื่อง AI บ้าง" ที่ต้องค้นและเทียบหลายคน

    เฉพาะผู้ที่ระบบต้นทางกำหนดให้เปิดเผยข้อมูลได้เท่านั้น
    ตู้ตั้งในที่สาธารณะ คนเดินผ่านมองเห็นจอ
    """
    if not text:
        return None

    flat = text.replace(" ", "")
    has_title = any(word.replace(" ", "") in flat for word in _PERSON_WORDS)

    rows = conn.execute(
        """
        SELECT * FROM personnel
        WHERE is_public = 1 AND fullname_th IS NOT NULL
        """
    ).fetchall()

    best: sqlite3.Row | None = None
    best_score = 0
    for row in rows:
        parts = (row["fullname_th"] or "").split()
        given = parts[0] if parts else ""
        surname = parts[1] if len(parts) > 1 else ""

        # นามสกุลตรงถือว่าเจาะจงพอแล้ว เพราะซ้ำกับคำทั่วไปได้ยากกว่าชื่อ
        if surname and surname in flat:
            score = 3 if given and given in flat else 2
        elif given and given in flat and has_title:
            score = 1
        else:
            continue

        if score > best_score:
            best, best_score = row, score

    if best is None:
        return None

    return {
        "name": f"{best['prefix'] or ''}{best['fullname_th']}".strip(),
        "nameEn": best["fullname_en"],
        "position": best["academic_position"],
        "adminPosition": best["administrative_position"],
        "type": best["personnel_type"],
        "education": best["education"],
        "email": best["email"],
        "phone": best["phone"],
        "expertise": best["expertise"],
    }


# คำย่อและคำไทยที่นักศึกษาใช้ กับคำเต็มที่เขียนไว้ในฐานข้อมูล
#
# ฐานข้อมูลเก็บความเชี่ยวชาญเป็นภาษาอังกฤษเต็มรูป เช่น "Internet of Things"
# แต่ไม่มีใครพูดแบบนั้น ทุกคนพูดว่า IoT หรือ "ไอโอที"
# ถ้าไม่มีตารางนี้ คำถามที่พบบ่อยที่สุดจะหาไม่เจอเลยสักคำ
TOPIC_ALIASES: dict[str, tuple[str, ...]] = {
    "artificial intelligence": ("ai", "เอไอ", "ปัญญาประดิษฐ์"),
    "internet of things": ("iot", "ไอโอที", "อินเทอร์เน็ตในทุกสิ่ง", "อินเตอร์เน็ตของสรรพสิ่ง"),
    "machine learning": ("ml", "แมชชีนเลิร์นนิง", "การเรียนรู้ของเครื่อง"),
    "deep learning": ("ดีปเลิร์นนิง", "การเรียนรู้เชิงลึก"),
    "data mining": ("เหมืองข้อมูล", "ดาต้าไมนิง"),
    "data science": ("วิทยาการข้อมูล", "ดาต้าไซแอนซ์"),
    "image processing": ("ประมวลผลภาพ", "ประมวลภาพ"),
    "database": ("ฐานข้อมูล", "ดาต้าเบส"),
    "network": ("เครือข่าย", "เน็ตเวิร์ก", "เน็ตเวิร์ค"),
    "block chain": ("บล็อกเชน", "blockchain", "บล็อคเชน"),
    "mobile applications": ("แอปมือถือ", "โมบายแอป", "แอปพลิเคชันมือถือ"),
    "software": ("ซอฟต์แวร์", "พัฒนาโปรแกรม"),
    "data structure": ("โครงสร้างข้อมูล",),
    "security": ("ความปลอดภัย", "ไซเบอร์"),
    "web": ("เว็บ", "เว็บไซต์"),
}


def _topic_hits(text: str) -> set[str]:
    """หัวข้อที่ถูกเอ่ยถึงในคำถาม คืนเป็นคำเต็มแบบที่ฐานข้อมูลเก็บไว้"""
    low = text.lower().replace(" ", "")
    found: set[str] = set()
    for canonical, aliases in TOPIC_ALIASES.items():
        if canonical.replace(" ", "") in low:
            found.add(canonical)
            continue
        for alias in aliases:
            if alias.replace(" ", "") in low:
                found.add(canonical)
                break
    return found


def search_personnel_by_topic(
    conn: sqlite3.Connection, text: str
) -> list[dict[str, Any]]:
    """หาอาจารย์ที่เชี่ยวชาญหัวข้อที่ถูกถามถึง

    ตอบจากคอลัมน์ความเชี่ยวชาญในตารางบุคลากรโดยตรง จึงได้ครบทุกคนเสมอ
    ต่างจากการให้ AI อ่านเอกสาร ซึ่งเห็นได้เท่าที่ค้นมาให้และอ้างอิงได้ทีละชิ้น
    คำถามแบบ "ใครสอนเรื่อง IoT บ้าง" จึงเคยได้คำตอบที่ขาดคนไปหลายคน
    """
    topics = _topic_hits(text)
    if not topics:
        return []

    matched = []
    for row in conn.execute(
        """
        SELECT * FROM personnel
        WHERE is_public = 1 AND expertise IS NOT NULL AND expertise != ''
        ORDER BY fullname_th
        """
    ).fetchall():
        expertise = row["expertise"].lower()
        hit = [t for t in topics if t.replace(" ", "") in expertise.replace(" ", "")]
        if hit:
            matched.append({
                "name": f"{row['prefix'] or ''}{row['fullname_th']}".strip(),
                "email": row["email"],
                "phone": row["phone"],
                "topics": sorted(hit),
                "expertise": row["expertise"],
            })
    return matched


def personnel_lines(person: dict[str, Any]) -> list[str]:
    """แปลงข้อมูลบุคลากรเป็นบรรทัดสำหรับแสดงบนจอ

    เรียงตามสิ่งที่นักศึกษามาหาบ่อยที่สุดก่อน คือช่องทางติดต่อ
    ความเชี่ยวชาญใส่ไว้ท้ายสุดเพราะยาวและอ่านข้ามได้
    """
    lines = [person["name"]]
    if person.get("position"):
        lines.append(person["position"])
    if person.get("email"):
        lines.append(f"อีเมล {person['email']}")
    if person.get("phone"):
        lines.append(f"โทร {person['phone']}")
    if person.get("education"):
        lines.append(f"การศึกษา {person['education']}")
    if person.get("expertise"):
        # ในฐานข้อมูลเก็บเป็นหลายบรรทัด แต่บนจอตู้ควรเป็นบรรทัดเดียว
        topics = " · ".join(t.strip() for t in person["expertise"].split("\n") if t.strip())
        if topics:
            lines.append(f"ความเชี่ยวชาญ {topics}")
    return lines


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
# ทะเบียนผู้ลงทะเบียนใบหน้า
#
# ข้อมูลใบหน้าเป็นข้อมูลชีวภาพตาม พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคลฯ มาตรา 26
# สาขาในฐานะผู้ควบคุมข้อมูลจึงต้องตอบได้เสมอว่า
#   เก็บข้อมูลของใครไว้บ้าง · เก็บเมื่อไร · ด้วยความยินยอมฉบับใด
# และต้องลบให้ได้เมื่อเจ้าของข้อมูลร้องขอ
# ------------------------------------------------------------
def registration_registry(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """รายชื่อผู้ที่มีข้อมูลใบหน้าอยู่ในระบบ พร้อมที่มาของความยินยอม"""
    rows = conn.execute(
        """
        SELECT s.student_id, s.name, s.year, s.program, s.is_synthetic,
               f.created_at AS registered_at, f.quality, f.model, f.dim,
               c.id AS consent_id, c.granted_at, c.policy_version, c.method
        FROM face_embeddings f
        JOIN students s ON s.id = f.student_id
        JOIN consents c ON c.id = f.consent_id AND c.revoked_at IS NULL
        ORDER BY f.created_at DESC
        """
    ).fetchall()

    return [
        {
            "studentId": r["student_id"],
            "name": r["name"],
            "year": r["year"],
            "program": r["program"],
            "isSynthetic": bool(r["is_synthetic"]),
            "registeredAt": r["registered_at"],
            "quality": r["quality"],
            "model": r["model"],
            "dim": r["dim"],
            "consentId": r["consent_id"],
            "consentGrantedAt": r["granted_at"],
            "policyVersion": r["policy_version"],
            "consentMethod": r["method"],
        }
        for r in rows
    ]


def student_record(conn: sqlite3.Connection, student_code: str) -> dict[str, Any] | None:
    """ข้อมูลทั้งหมดที่ระบบเก็บไว้เกี่ยวกับนักศึกษาหนึ่งคน

    ใช้ตอบคำขอ "ขอดูข้อมูลของฉัน" ตามสิทธิของเจ้าของข้อมูล
    เวกเตอร์ใบหน้าไม่ถูกส่งออกมาเป็นตัวเลข เพราะเป็นข้อมูลชีวภาพ
    บอกเพียงว่ามีอยู่กี่รายการ เก็บเมื่อไร และใช้โมเดลใด
    """
    student = find_student_by_code(conn, student_code)
    if student is None:
        return None

    consents = conn.execute(
        """SELECT id, purpose, policy_version, granted_at, revoked_at, method
           FROM consents WHERE student_id = ? ORDER BY id""",
        (student["id"],),
    ).fetchall()

    faces = conn.execute(
        """SELECT id, consent_id, dim, model, quality, created_at
           FROM face_embeddings WHERE student_id = ? ORDER BY id""",
        (student["id"],),
    ).fetchall()

    term = get_current_term(conn)
    schedule = get_schedule(conn, student["id"], term["id"]) if term else []

    return {
        "student": {
            "studentId": student["student_id"],
            "name": student["name"],
            "year": student["year"],
            "program": student["program"],
            "advisor": student["advisor"],
            "isSynthetic": bool(student["is_synthetic"]),
            "createdAt": student["created_at"],
        },
        "consents": [
            {
                "id": c["id"],
                "purpose": c["purpose"],
                "policyVersion": c["policy_version"],
                "grantedAt": c["granted_at"],
                "revokedAt": c["revoked_at"],
                "method": c["method"],
            }
            for c in consents
        ],
        "faceEmbeddings": [
            {
                "id": f["id"],
                "consentId": f["consent_id"],
                "dimensions": f["dim"],
                "model": f["model"],
                "quality": f["quality"],
                "createdAt": f["created_at"],
                "note": "เก็บเป็นค่าเวกเตอร์เท่านั้น ไม่มีภาพใบหน้า และย้อนกลับเป็นภาพไม่ได้",
            }
            for f in faces
        ],
        "enrolledCourses": len(schedule),
    }


def forget_student(conn: sqlite3.Connection, student_code: str, now: str) -> dict[str, Any] | None:
    """ลบข้อมูลใบหน้าและถอนความยินยอมของนักศึกษาหนึ่งคน

    ใช้เมื่อเจ้าของข้อมูลมาขอลบที่สำนักงานสาขา
    จำเป็นต้องมีช่องทางนี้ เพราะการลบผ่านหน้าตู้ต้องยืนยันตัวตนด้วยใบหน้าก่อน
    ถ้าระบบจำหน้าไม่ได้ เจ้าของข้อมูลจะลบข้อมูลตัวเองไม่ได้เลย

    เก็บบันทึกการถอนความยินยอมไว้เป็นหลักฐาน แต่ลบเวกเตอร์ทิ้งจริง
    """
    student = find_student_by_code(conn, student_code)
    if student is None:
        return None

    with conn:
        revoked = conn.execute(
            """UPDATE consents SET revoked_at = ?
               WHERE student_id = ? AND purpose = 'face_recognition' AND revoked_at IS NULL""",
            (now, student["id"]),
        ).rowcount
        deleted = conn.execute(
            "DELETE FROM face_embeddings WHERE student_id = ?", (student["id"],)
        ).rowcount

    return {
        "studentId": student["student_id"],
        "name": student["name"],
        "vectorsDeleted": deleted,
        "consentsRevoked": revoked,
        "at": now,
    }


def orphan_consents(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """ความยินยอมที่ไม่มีเวกเตอร์ใบหน้าผูกอยู่และยังไม่ถูกถอน

    เกิดจากผู้ใช้กดยินยอมแล้วเดินจากไปก่อนถ่ายเสร็จ
    ปล่อยค้างไว้ไม่ได้ เพราะเป็นบันทึกว่า "ผู้นี้ยินยอมให้เก็บข้อมูลชีวภาพ"
    ทั้งที่ระบบไม่ได้เก็บอะไรไว้จริง
    """
    rows = conn.execute(
        """
        SELECT c.id, c.granted_at, c.policy_version, s.student_id, s.name
        FROM consents c
        JOIN students s ON s.id = c.student_id
        LEFT JOIN face_embeddings f ON f.consent_id = c.id
        WHERE c.revoked_at IS NULL AND f.id IS NULL
        ORDER BY c.id
        """
    ).fetchall()
    return [
        {
            "id": r["id"],
            "studentId": r["student_id"],
            "name": r["name"],
            "grantedAt": r["granted_at"],
            "policyVersion": r["policy_version"],
        }
        for r in rows
    ]


def clear_orphan_consents(conn: sqlite3.Connection, now: str) -> int:
    """ถอนความยินยอมที่ค้างอยู่โดยไม่มีข้อมูลใดผูกไว้"""
    ids = [c["id"] for c in orphan_consents(conn)]
    if not ids:
        return 0
    with conn:
        conn.executemany(
            "UPDATE consents SET revoked_at = ? WHERE id = ?",
            [(now, cid) for cid in ids],
        )
    return len(ids)


def upsert_student(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    name: str,
    year: int | None,
    program: str | None,
    advisor: str | None,
    now: str,
) -> str:
    """เพิ่มหรืออัปเดตนักศึกษาหนึ่งคน คืนค่า 'added' หรือ 'updated'

    ใช้กับการนำเข้ารายชื่อจากสาขา ไม่ลบใครออกโดยอัตโนมัติ
    เพราะการลบนักศึกษาจะลบเวกเตอร์ใบหน้าตามไปด้วย (ON DELETE CASCADE)
    ซึ่งต้องเป็นการตัดสินใจของคน ไม่ใช่ผลข้างเคียงของการนำเข้าไฟล์
    """
    existing = find_student_by_code(conn, student_id)
    conn.execute(
        """INSERT INTO students (student_id, name, year, program, advisor, is_synthetic, created_at)
           VALUES (?, ?, ?, ?, ?, 0, ?)
           ON CONFLICT(student_id) DO UPDATE SET
               name = excluded.name,
               year = excluded.year,
               program = excluded.program,
               advisor = excluded.advisor,
               is_synthetic = 0""",
        (student_id, name, year, program, advisor, now),
    )
    return "updated" if existing is not None else "added"


def upsert_roster_student(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    prefix: str | None,
    name: str,
    year: int | None,
    entry_year: int | None,
    program: str | None,
    program_code: str | None,
    status_code: str | None,
    status_label: str | None,
    active: bool,
    now: str,
) -> str:
    """เพิ่มหรืออัปเดตนักศึกษาจากรายชื่อของระบบทะเบียน

    ไม่แตะคอลัมน์ advisor เพราะรายงานรายชื่อไม่มีข้อมูลอาจารย์ที่ปรึกษา
    ถ้าเขียนทับด้วยค่าว่าง ข้อมูลที่กรอกไว้จากแหล่งอื่นจะหายไป
    """
    existing = find_student_by_code(conn, student_id)
    conn.execute(
        """INSERT INTO students
               (student_id, prefix, name, year, entry_year, program, program_code,
                status_code, status_label, active, is_synthetic, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
           ON CONFLICT(student_id) DO UPDATE SET
               prefix = excluded.prefix,
               name = excluded.name,
               year = excluded.year,
               entry_year = excluded.entry_year,
               program = excluded.program,
               program_code = excluded.program_code,
               status_code = excluded.status_code,
               status_label = excluded.status_label,
               active = excluded.active,
               is_synthetic = 0,
               updated_at = excluded.updated_at""",
        (student_id, prefix, name, year, entry_year, program, program_code,
         status_code, status_label, 1 if active else 0, now, now),
    )
    return "updated" if existing is not None else "added"


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
