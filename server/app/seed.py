"""เตรียมฐานข้อมูลสำหรับพัฒนาและสาธิต

    python -m app.seed              # นำเข้าข้อมูลจริง + สร้างข้อมูลสาธิต
    python -m app.seed --reset      # ลบฐานข้อมูลเดิมแล้วทำใหม่
    python -m app.seed --real-only  # นำเข้าเฉพาะข้อมูลจริง (สำหรับตู้ที่ให้บริการจริง)

ไฟล์นี้สร้างเฉพาะสิ่งที่ยังไม่มีข้อมูลจริง ได้แก่ นักศึกษา ตารางเรียน และกำหนดสอบ
ส่วนที่เหลือมาจาก csmju_dataset ผ่าน app.import_csmju

ตารางเรียนที่สร้างขึ้นใช้ "ห้องจริงและรายวิชาจริง" มีเพียงการจับคู่วัน เวลา
และผู้สอนเท่านั้นที่สมมติขึ้น ทุกแถวถูกทำเครื่องหมาย is_synthetic = 1
และหน้าจอจะขึ้นป้ายเตือนให้ผู้ใช้ทราบ

เมื่อได้ตารางเรียนจริงจากสาขาแล้ว ให้เขียนสคริปต์นำเข้าแยกต่างหาก
โดยใช้โครงตารางเดียวกันนี้และตั้ง is_synthetic = 0
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from . import config, db as db_module, thai
from .import_csmju import DEFAULT_DATASET, import_all

TERM = {
    "code": "2569-1",
    "label": "ภาคการศึกษาที่ 1 ปีการศึกษา 2569",
    "data_updated_at": "2026-09-22T06:00:00+07:00",
}

# รายวิชาจริงจากหลักสูตรวิทยาการคอมพิวเตอร์ (รหัสตรงกับ courses ที่นำเข้ามา)
# (วัน, เริ่ม, จบ, รหัสวิชา, รหัสห้อง, ผู้สอน)
# ผู้สอนเป็นบุคลากรจริงของสาขา แต่การจับคู่วิชา–ผู้สอน–เวลา เป็นการสมมติ
SECTIONS = [
    (1, "09:00", "12:00", "10301141-68", "6", "ผศ.ภานุวัฒน์ เมฆะ"),
    (1, "13:00", "15:00", "10301222-68", "8", "ผศ.ดร.พาสน์ ปราโมกข์ชน"),
    (1, "10:00", "12:00", "10301231-68", "7", "ผศ.ดร.ปวีณ เขื่อนแก้ว"),
    (2, "10:00", "12:00", "10301231-68", "7", "ผศ.ดร.ปวีณ เขื่อนแก้ว"),
    (2, "08:00", "11:00", "10301349", "5", "ผศ.ดร.พาสน์ ปราโมกข์ชน"),
    (2, "13:00", "15:00", "10301222-68", "8", "ผศ.ดร.พาสน์ ปราโมกข์ชน"),
    (3, "08:00", "10:00", "10301151", "2", "ผศ.ภานุวัฒน์ เมฆะ"),
    (3, "10:00", "12:00", "10301357-68", "2", "ผศ.ภานุวัฒน์ เมฆะ"),
    (3, "13:00", "16:00", "10301243", "1", "ผศ.ดร.ปวีณ เขื่อนแก้ว"),
    (3, "13:00", "16:00", "10301337", "3", "ผศ.ดร.ปวีณ เขื่อนแก้ว"),
    (4, "09:00", "12:00", "10301341-68", "4", "ผศ.ดร.พาสน์ ปราโมกข์ชน"),
    (4, "13:00", "15:00", "10301354-68", "2", "ผศ.ภานุวัฒน์ เมฆะ"),
    (5, "09:00", "12:00", "10301338", "9", "ผศ.ดร.ปวีณ เขื่อนแก้ว"),
    (5, "13:00", "16:00", "10301337", "3", "ผศ.ดร.ปวีณ เขื่อนแก้ว"),
]

STUDENTS = [
    {
        "student_id": "6604101001",
        "name": "สมชาย ใจดี",
        "year": 3,
        "program": "วิทยาการคอมพิวเตอร์",
        "advisor": "ผศ.ดร.พาสน์ ปราโมกข์ชน",
        # (วัน, เวลาเริ่ม, รหัสวิชา) ชี้ไปยังคาบใน SECTIONS
        "sections": [
            (1, "09:00", "10301141-68"), (1, "13:00", "10301222-68"),
            (2, "10:00", "10301231-68"), (3, "08:00", "10301151"),
            (3, "10:00", "10301357-68"), (3, "13:00", "10301243"),
            (4, "09:00", "10301341-68"), (5, "09:00", "10301338"),
        ],
    },
    {
        "student_id": "6604101388",
        "name": "ปาริชาต แสงทอง",
        "year": 3,
        "program": "วิทยาการคอมพิวเตอร์",
        "advisor": "ผศ.ภานุวัฒน์ เมฆะ",
        "sections": [
            (1, "10:00", "10301231-68"), (2, "08:00", "10301349"),
            (2, "13:00", "10301222-68"), (3, "13:00", "10301337"),
            (4, "09:00", "10301341-68"), (4, "13:00", "10301354-68"),
            (5, "13:00", "10301337"),
        ],
    },
]

# (รหัสวิชา, ประเภท, วันที่, เวลาเริ่ม, เวลาจบ, รหัสห้อง)
EXAMS = [
    ("10301141-68", "สอบกลางภาค", "2026-10-12", "09:00", "11:00", "6"),
    ("10301222-68", "สอบกลางภาค", "2026-10-14", "13:00", "15:00", "8"),
    ("10301231-68", "สอบกลางภาค", "2026-10-16", "09:00", "11:00", "7"),
    ("10301349", "สอบกลางภาค", "2026-10-13", "09:00", "11:00", "5"),
    ("10301354-68", "สอบกลางภาค", "2026-10-15", "13:00", "15:00", "2"),
    ("10301337", "สอบกลางภาค", "2026-10-19", "09:00", "11:00", "3"),
]

# (id, ข้อความบนปุ่ม, ประเภทคำถาม, แหล่งคำตอบ, ต้องยืนยันตัวตน, ลำดับ)
QUICK_QUESTIONS = [
    ("room-floor", "ห้องนี้อยู่ชั้นไหน", "ตำแหน่งห้องเรียน", "db", 1, 10),
    ("contact-teacher", "ติดต่ออาจารย์ที่ไหน", "ติดต่ออาจารย์", "db", 0, 20),
    ("exam-subject", "กำหนดสอบวิชานี้", "กำหนดสอบ", "db", 1, 30),
    ("next-class", "คาบต่อไปเรียนที่ไหน", "ตารางเรียน", "db", 1, 40),
    ("office-contact", "ติดต่อสำนักงานสาขาอย่างไร", "บริการสำนักงาน", "db", 0, 50),
    ("add-drop", "เพิ่ม–ถอนรายวิชาทำอย่างไร", "ระเบียบการศึกษา", "ai", 0, 60),
    ("coop", "สหกิจศึกษาต้องเตรียมอะไร", "สหกิจศึกษา", "ai", 0, 70),
    ("curriculum", "หลักสูตรเรียนอะไรบ้าง", "หลักสูตร", "ai", 0, 80),
    ("facilities", "สาขามีห้องปฏิบัติการอะไรบ้าง", "อาคารสถานที่", "ai", 0, 90),
    ("scholarship-detail", "ทุนวิจัยระดับปริญญาตรีมีเท่าไร", "ทุนการศึกษา", "none", 0, 100),
]


def seed_quick_questions(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM quick_questions")
    for qid, label, kind, source, personal, order in QUICK_QUESTIONS:
        conn.execute(
            """INSERT INTO quick_questions (id, label, kind, source, personal, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (qid, label, kind, source, personal, order),
        )


def seed_term(conn: sqlite3.Connection) -> int:
    conn.execute(
        """INSERT INTO terms (code, label, is_current, data_updated_at)
           VALUES (:code, :label, 1, :data_updated_at)
           ON CONFLICT(code) DO UPDATE SET
               label = excluded.label, data_updated_at = excluded.data_updated_at""",
        TERM,
    )
    return conn.execute("SELECT id FROM terms WHERE code = ?", (TERM["code"],)).fetchone()["id"]


def seed_demo_schedule(conn: sqlite3.Connection, term_id: int) -> None:
    """สร้างตารางเรียนสาธิตบนห้องจริงและรายวิชาจริง"""
    now = thai.now().isoformat(timespec="seconds")

    def course_id(code: str) -> int:
        row = conn.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone()
        if row is None:
            raise ValueError(f"ไม่พบรายวิชา {code} — นำเข้าข้อมูลจริงก่อนด้วย app.import_csmju")
        return row["id"]

    def room_id(code: str) -> int:
        row = conn.execute("SELECT id FROM rooms WHERE code = ?", (code,)).fetchone()
        if row is None:
            raise ValueError(f"ไม่พบห้อง {code} — นำเข้าข้อมูลจริงก่อนด้วย app.import_csmju")
        return row["id"]

    for day, start, end, course, room, teacher in SECTIONS:
        conn.execute(
            """INSERT INTO sections
                   (term_id, course_id, room_id, day, start_time, end_time, teacher, is_synthetic)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)
               ON CONFLICT(term_id, course_id, day, start_time) DO UPDATE SET
                   room_id = excluded.room_id, end_time = excluded.end_time,
                   teacher = excluded.teacher""",
            (term_id, course_id(course), room_id(room), day, start, end, teacher),
        )

    for student in STUDENTS:
        conn.execute(
            """INSERT INTO students
                   (student_id, name, year, program, advisor, is_synthetic, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)
               ON CONFLICT(student_id) DO UPDATE SET
                   name = excluded.name, year = excluded.year,
                   program = excluded.program, advisor = excluded.advisor""",
            (student["student_id"], student["name"], student["year"],
             student["program"], student["advisor"], now),
        )
        pk = conn.execute(
            "SELECT id FROM students WHERE student_id = ?", (student["student_id"],)
        ).fetchone()["id"]

        conn.execute("DELETE FROM enrollments WHERE student_id = ?", (pk,))
        for day, start, course in student["sections"]:
            row = conn.execute(
                """SELECT id FROM sections
                   WHERE term_id = ? AND course_id = ? AND day = ? AND start_time = ?""",
                (term_id, course_id(course), day, start),
            ).fetchone()
            if row is None:
                raise ValueError(f"ไม่พบคาบเรียน {course} วัน {day} เวลา {start}")
            conn.execute(
                "INSERT OR IGNORE INTO enrollments (student_id, section_id) VALUES (?, ?)",
                (pk, row["id"]),
            )

    for course, kind, date_, start, end, room in EXAMS:
        conn.execute(
            """INSERT INTO exams
                   (term_id, course_id, room_id, exam_type, exam_date,
                    start_time, end_time, is_synthetic)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)
               ON CONFLICT(term_id, course_id, exam_type) DO UPDATE SET
                   room_id = excluded.room_id, exam_date = excluded.exam_date,
                   start_time = excluded.start_time, end_time = excluded.end_time""",
            (term_id, course_id(course), room_id(room), kind, date_, start, end),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="เตรียมฐานข้อมูลของตู้บริการข้อมูล")
    parser.add_argument("--reset", action="store_true", help="ลบฐานข้อมูลเดิมแล้วสร้างใหม่")
    parser.add_argument("--real-only", action="store_true",
                        help="นำเข้าเฉพาะข้อมูลจริง ไม่สร้างนักศึกษาและตารางเรียนสาธิต")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    args = parser.parse_args(argv)

    if args.reset and config.DB_PATH.exists():
        config.DB_PATH.unlink()
        for suffix in ("-wal", "-shm"):
            config.DB_PATH.with_name(config.DB_PATH.name + suffix).unlink(missing_ok=True)
        print(f"ลบฐานข้อมูลเดิม: {config.DB_PATH}")

    conn = db_module.connect()
    db_module.init_db(conn)

    stats = import_all(conn, args.dataset)
    print(f"ข้อมูลจริงจากเว็บไซต์สาขา (เก็บเมื่อ {(stats['crawled_at'] or '')[:10]})")
    for key in ("buildings", "rooms", "personnel", "courses", "contacts",
                "announcements", "doc_chunks"):
        print(f"  {key:16s} {stats[key]:5d}")

    with db_module.transaction(conn):
        seed_quick_questions(conn)
        term_id = seed_term(conn)
        if not args.real_only:
            seed_demo_schedule(conn, term_id)

    if args.real_only:
        print("\nข้ามข้อมูลสาธิต (--real-only) — ตู้จะยังไม่มีตารางเรียนให้แสดง")
    else:
        counts = {
            name: conn.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()["n"]
            for name in ("students", "sections", "enrollments", "exams")
        }
        print("\nข้อมูลสาธิต (สมมติ — ใช้ห้องจริงและรายวิชาจริง)")
        for name, n in counts.items():
            print(f"  {name:16s} {n:5d}")
        print("  ทุกแถวถูกทำเครื่องหมาย is_synthetic = 1 และหน้าจอจะขึ้นป้ายเตือน")

    conn.close()
    print(f"\nฐานข้อมูล: {config.DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
