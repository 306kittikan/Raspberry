"""นำเข้าข้อมูลตั้งต้นลงฐานข้อมูล

    python -m app.seed            # สร้าง/เติมข้อมูล (ข้ามของที่มีแล้ว)
    python -m app.seed --reset    # ลบฐานข้อมูลเดิมแล้วสร้างใหม่

ข้อมูลชุดนี้ย้ายมาจาก web/src/data/mockData.js ที่ใช้ตอนทำต้นแบบหน้าจอ
เมื่อสาขาส่งไฟล์ตารางเรียนจริงมา ให้เขียนสคริปต์นำเข้าแยกต่างหาก
โดยใช้โครงตารางเดียวกันนี้ ไม่ต้องแก้ไฟล์นี้
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from . import config, db as db_module, thai

# ------------------------------------------------------------
# ข้อมูลสาขาและภาคการศึกษา
# ------------------------------------------------------------
DEPARTMENT = {
    "name": "สาขาวิชาวิทยาการคอมพิวเตอร์",
    "faculty": "คณะวิทยาศาสตร์ มหาวิทยาลัยแม่โจ้",
    "abbr": "CS",
    "office_location": "สำนักงานสาขาวิชาฯ ชั้น 2 อาคารจุฬาภรณ์",
    "office_hours": "จันทร์–ศุกร์ 08.30–16.30 น.",
    "office_phone": "053-873-870",
    "office_email": "cs@mju.ac.th",
}

TERM = {
    "code": "2569-1",
    "label": "ภาคการศึกษาที่ 1 ปีการศึกษา 2569",
    "data_updated_at": "2026-09-22T06:00:00+07:00",
}

ANNOUNCEMENTS = [
    ("ลงทะเบียน", "เปิดลงทะเบียนเพิ่ม–ถอนรายวิชา",
     "ถึงวันศุกร์ที่ 3 ตุลาคม 2569 ผ่านระบบ ERP ของมหาวิทยาลัย", None, "2026-10-03"),
    ("สหกิจศึกษา", "ปฐมนิเทศสหกิจศึกษา รุ่นที่ 12",
     "วันพุธที่ 8 ตุลาคม 2569 เวลา 13.00 น. ห้องประชุมจุฬาภรณ์ ชั้น 3", None, "2026-10-08"),
    ("กิจกรรม", "MJU CS Hackathon 2026 เปิดรับสมัครทีม",
     "ทีมละ 3 คน สมัครได้ถึง 30 กันยายน 2569 ที่สำนักงานสาขาวิชาฯ", None, "2026-09-30"),
    ("ทุนการศึกษา", "ทุนช่วยเหลือนักศึกษา ภาคเรียนที่ 1/2569",
     "ยื่นเอกสารที่งานกิจการนักศึกษา ภายใน 10 ตุลาคม 2569", None, "2026-10-10"),
]

# code → (อาคาร, ชั้น, คำแนะนำการเดินทาง)
ROOMS = {
    "ศว 2301": ("อาคารจุฬาภรณ์", 3, "ขึ้นลิฟต์ฝั่งซ้ายของโถงทางเข้า แล้วเลี้ยวขวา"),
    "ศว 2202": ("อาคารจุฬาภรณ์", 2, "ขึ้นบันไดกลาง แล้วเลี้ยวซ้ายสุดทางเดิน"),
    "ศว 2204": ("อาคารจุฬาภรณ์", 2, None),
    "ศว 2305": ("อาคารจุฬาภรณ์", 3, None),
    "ศว 2401": ("อาคารจุฬาภรณ์", 4, None),
    "ศว 2403": ("อาคารจุฬาภรณ์", 4, None),
    "ศว 3105": ("อาคารจุฬาภรณ์", 1, None),
    "ศว 3202": ("อาคารจุฬาภรณ์", 2, None),
    "ศว 3301": ("อาคารจุฬาภรณ์", 3, None),
    "ศว 1101": ("อาคารวิทยาศาสตร์", 1, None),
    "ศศ 1105": ("อาคารศิลปศาสตร์", 1, None),
    "ศศ 1203": ("อาคารศิลปศาสตร์", 2, None),
}

COURSES = {
    "ทว 331": "การเขียนโปรแกรมบนเว็บ",
    "ทว 322": "ระบบฐานข้อมูล",
    "ทว 341": "ปัญญาประดิษฐ์เบื้องต้น",
    "ทว 351": "เครือข่ายคอมพิวเตอร์",
    "ทว 352": "ปฏิบัติการเครือข่ายคอมพิวเตอร์",
    "ทว 355": "ความมั่นคงปลอดภัยไซเบอร์",
    "ทว 361": "วิศวกรรมซอฟต์แวร์",
    "ทว 371": "การวิเคราะห์ข้อมูลขนาดใหญ่",
    "ทว 381": "ปฏิสัมพันธ์ระหว่างมนุษย์กับคอมพิวเตอร์",
    "ทว 497": "โครงงานวิทยาการคอมพิวเตอร์ 1",
    "คณ 211": "คณิตศาสตร์ดิสครีต",
    "ศท 141": "ภาษาอังกฤษสำหรับงานคอมพิวเตอร์",
    "ศท 142": "การสื่อสารเชิงวิชาชีพ",
}

# (day, start, end, course_code, room_code, teacher)
SECTIONS = [
    (1, "09:00", "12:00", "ทว 331", "ศว 2301", "อ.ดร. ธนากร พงศ์พันธุ์"),
    (1, "13:00", "15:00", "ทว 322", "ศว 2202", "ผศ.ดร. วราภรณ์ สุขสวัสดิ์"),
    (1, "10:00", "12:00", "ทว 341", "ศว 3105", "อ.ดร. ปรีชา วงศ์คำ"),
    (2, "10:00", "12:00", "ทว 341", "ศว 3105", "อ.ดร. ปรีชา วงศ์คำ"),
    (2, "08:00", "11:00", "ทว 371", "ศว 2305", "อ.ดร. ธนากร พงศ์พันธุ์"),
    (2, "13:00", "15:00", "ทว 322", "ศว 2202", "ผศ.ดร. วราภรณ์ สุขสวัสดิ์"),
    (2, "15:00", "17:00", "ศท 142", "ศศ 1105", "อ. มาลี ทองคำ"),
    (3, "08:00", "10:00", "คณ 211", "ศว 1101", "อ. สุนิสา ปัญญาดี"),
    (3, "10:00", "12:00", "ทว 351", "ศว 2204", "อ.ดร. ณัฐพล อินต๊ะ"),
    (3, "13:00", "16:00", "ทว 352", "ศว 2401", "อ.ดร. ณัฐพล อินต๊ะ"),
    (3, "13:00", "16:00", "ทว 381", "ศว 2403", "ผศ. กิตติพงษ์ ศรีวิชัย"),
    (4, "09:00", "12:00", "ทว 361", "ศว 3202", "ผศ. กิตติพงษ์ ศรีวิชัย"),
    (4, "13:00", "15:00", "ศท 141", "ศศ 1203", "อ. Emily Carter"),
    (4, "13:00", "15:00", "ทว 355", "ศว 2204", "อ.ดร. ณัฐพล อินต๊ะ"),
    (5, "09:00", "12:00", "ทว 497", "ศว 3301", "ผศ.ดร. วราภรณ์ สุขสวัสดิ์"),
    (5, "13:00", "16:00", "ทว 497", "ศว 3301", "อ.ดร. ธนากร พงศ์พันธุ์"),
]

STUDENTS = [
    {
        "student_id": "6604101001",
        "name": "สมชาย ใจดี",
        "year": 3,
        "program": "วิทยาการคอมพิวเตอร์",
        "advisor": "ผศ.ดร. วราภรณ์ สุขสวัสดิ์",
        # (day, start, course_code) — ชี้ไปยังคาบใน SECTIONS
        "sections": [
            (1, "09:00", "ทว 331"), (1, "13:00", "ทว 322"), (2, "10:00", "ทว 341"),
            (3, "08:00", "คณ 211"), (3, "10:00", "ทว 351"), (3, "13:00", "ทว 352"),
            (4, "09:00", "ทว 361"), (4, "13:00", "ศท 141"), (5, "09:00", "ทว 497"),
        ],
    },
    {
        "student_id": "6604101388",
        "name": "ปาริชาต แสงทอง",
        "year": 3,
        "program": "วิทยาการคอมพิวเตอร์",
        "advisor": "อ.ดร. ธนากร พงศ์พันธุ์",
        "sections": [
            (1, "10:00", "ทว 341"), (2, "08:00", "ทว 371"), (2, "13:00", "ทว 322"),
            (2, "15:00", "ศท 142"), (3, "13:00", "ทว 381"), (4, "09:00", "ทว 361"),
            (4, "13:00", "ทว 355"), (5, "13:00", "ทว 497"),
        ],
    },
]

# (course_code, ประเภท, วันที่, เวลาเริ่ม, เวลาจบ, ห้องสอบ)
EXAMS = [
    ("ทว 331", "สอบกลางภาค", "2026-10-12", "09:00", "11:00", "ศว 2301"),
    ("ทว 322", "สอบกลางภาค", "2026-10-14", "13:00", "15:00", "ศว 2202"),
    ("ทว 341", "สอบกลางภาค", "2026-10-16", "09:00", "11:00", "ศว 3105"),
    ("ทว 371", "สอบกลางภาค", "2026-10-13", "09:00", "11:00", "ศว 2305"),
    ("ทว 355", "สอบกลางภาค", "2026-10-15", "13:00", "15:00", "ศว 2204"),
    ("ทว 381", "สอบกลางภาค", "2026-10-19", "09:00", "11:00", "ศว 2403"),
]

# (id, label, kind, source, personal, ลำดับ)
QUICK_QUESTIONS = [
    ("room-floor", "ห้องนี้อยู่ชั้นไหน", "ตำแหน่งห้องเรียน", "db", 1, 10),
    ("contact-teacher", "ติดต่ออาจารย์ที่ไหน", "ติดต่ออาจารย์", "db", 0, 20),
    ("exam-subject", "กำหนดสอบวิชานี้", "กำหนดสอบ", "db", 1, 30),
    ("next-class", "คาบต่อไปเรียนที่ไหน", "ตารางเรียน", "db", 1, 40),
    ("office-hours", "สำนักงานสาขาเปิดกี่โมง", "บริการสำนักงาน", "db", 0, 50),
    ("add-drop", "เพิ่ม–ถอนรายวิชาทำอย่างไร", "ระเบียบการศึกษา", "ai", 0, 60),
    ("coop", "สหกิจศึกษาต้องเตรียมอะไร", "สหกิจศึกษา", "ai", 0, 70),
    ("wifi", "ใช้ Wi-Fi มหาวิทยาลัยอย่างไร", "บริการไอที", "ai", 0, 80),
    ("scholarship-detail", "ทุนวิจัยระดับปริญญาตรีมีเท่าไร", "ทุนการศึกษา", "none", 0, 90),
]

# เอกสารอ้างอิงของผู้ช่วย AI
# (ชื่อเอกสาร, ข้อความอ้างอิงที่แสดงบนจอ, วันที่มีผล, [(หน้า, เนื้อหา), ...])
DOCUMENTS = [
    (
        "คู่มือนักศึกษา ปีการศึกษา 2569",
        "คู่มือนักศึกษา ปีการศึกษา 2569",
        "2026-06-01",
        [
            (
                "หน้า 18",
                "การเพิ่มและถอนรายวิชา นักศึกษายื่นคำร้องผ่านระบบ ERP ของมหาวิทยาลัย "
                "ภายในสองสัปดาห์แรกของภาคการศึกษา คำร้องต้องได้รับความเห็นชอบจาก "
                "อาจารย์ที่ปรึกษาก่อนจึงจะบันทึกผลได้ หากพ้นกำหนดให้ยื่นคำร้องพิเศษ "
                "ที่สำนักงานสาขาวิชาฯ พร้อมเหตุผลประกอบ",
            ),
            (
                "หน้า 24",
                "การลาพักการศึกษา นักศึกษาต้องยื่นคำร้องก่อนวันสุดท้ายของการลงทะเบียน "
                "และชำระค่าธรรมเนียมรักษาสภาพนักศึกษาทุกภาคการศึกษาที่ลาพัก",
            ),
        ],
    ),
    (
        "ประกาศสาขาวิชาฯ เรื่องสหกิจศึกษา ฉบับที่ 3/2569",
        "ประกาศสาขาวิชาฯ เรื่องสหกิจศึกษา ฉบับที่ 3/2569",
        "2026-07-15",
        [
            (
                None,
                "คุณสมบัติผู้เข้าร่วมสหกิจศึกษา ต้องผ่านรายวิชาบังคับไม่น้อยกว่า 90 หน่วยกิต "
                "และมีเกรดเฉลี่ยสะสมไม่ต่ำกว่า 2.00 เอกสารที่ต้องเตรียมได้แก่ ใบสมัคร "
                "แฟ้มสะสมผลงาน และหนังสือขอความอนุเคราะห์จากสาขาวิชาฯ "
                "นักศึกษาต้องเข้าร่วมปฐมนิเทศสหกิจศึกษาก่อนออกปฏิบัติงานทุกครั้ง",
            ),
        ],
    ),
    (
        "คู่มือการใช้งานเครือข่าย MJU-WiFi ฉบับปี 2569",
        "คู่มือการใช้งานเครือข่าย MJU-WiFi ฉบับปี 2569",
        "2026-05-01",
        [
            (
                None,
                "การเชื่อมต่อเครือข่ายไร้สายของมหาวิทยาลัย เลือกเครือข่ายชื่อ MJU-WiFi "
                "แล้วเข้าสู่ระบบด้วยบัญชีอินเทอร์เน็ตของมหาวิทยาลัย "
                "หนึ่งบัญชีเชื่อมต่อพร้อมกันได้สูงสุด 3 อุปกรณ์ "
                "หากเข้าใช้งานไม่ได้ให้ติดต่อศูนย์เทคโนโลยีสารสนเทศ ชั้น 1 อาคารสำนักหอสมุด",
            ),
        ],
    ),
]


# ------------------------------------------------------------
def seed(conn: sqlite3.Connection) -> None:
    now = thai.now().isoformat(timespec="seconds")

    with db_module.transaction(conn):
        conn.execute(
            """INSERT OR REPLACE INTO department
               (id, name, faculty, abbr, office_location, office_hours, office_phone, office_email)
               VALUES (1, :name, :faculty, :abbr, :office_location, :office_hours,
                       :office_phone, :office_email)""",
            DEPARTMENT,
        )

        conn.execute(
            """INSERT INTO terms (code, label, is_current, data_updated_at)
               VALUES (:code, :label, 1, :data_updated_at)
               ON CONFLICT(code) DO UPDATE SET
                   label = excluded.label,
                   data_updated_at = excluded.data_updated_at""",
            TERM,
        )
        term_id = conn.execute(
            "SELECT id FROM terms WHERE code = ?", (TERM["code"],)
        ).fetchone()["id"]

        conn.execute("DELETE FROM announcements")
        for order, (tag, title, detail, starts, ends) in enumerate(ANNOUNCEMENTS):
            conn.execute(
                """INSERT INTO announcements (tag, title, detail, starts_on, ends_on, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tag, title, detail, starts, ends, order),
            )

        for code, (building, floor, directions) in ROOMS.items():
            conn.execute(
                """INSERT INTO rooms (code, building, floor, directions) VALUES (?, ?, ?, ?)
                   ON CONFLICT(code) DO UPDATE SET
                       building = excluded.building,
                       floor = excluded.floor,
                       directions = excluded.directions""",
                (code, building, floor, directions),
            )

        for code, name in COURSES.items():
            conn.execute(
                """INSERT INTO courses (code, name) VALUES (?, ?)
                   ON CONFLICT(code) DO UPDATE SET name = excluded.name""",
                (code, name),
            )

        def course_id(code: str) -> int:
            return conn.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone()["id"]

        def room_id(code: str) -> int:
            return conn.execute("SELECT id FROM rooms WHERE code = ?", (code,)).fetchone()["id"]

        for day, start, end, course, room, teacher in SECTIONS:
            conn.execute(
                """INSERT INTO sections
                       (term_id, course_id, room_id, day, start_time, end_time, teacher)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(term_id, course_id, day, start_time) DO UPDATE SET
                       room_id = excluded.room_id,
                       end_time = excluded.end_time,
                       teacher = excluded.teacher""",
                (term_id, course_id(course), room_id(room), day, start, end, teacher),
            )

        for student in STUDENTS:
            conn.execute(
                """INSERT INTO students (student_id, name, year, program, advisor, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
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
                       (term_id, course_id, room_id, exam_type, exam_date, start_time, end_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(term_id, course_id, exam_type) DO UPDATE SET
                       room_id = excluded.room_id, exam_date = excluded.exam_date,
                       start_time = excluded.start_time, end_time = excluded.end_time""",
                (term_id, course_id(course), room_id(room), kind, date_, start, end),
            )

        for qid, label, kind, source, personal, order in QUICK_QUESTIONS:
            conn.execute(
                """INSERT INTO quick_questions (id, label, kind, source, personal, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       label = excluded.label, kind = excluded.kind,
                       source = excluded.source, personal = excluded.personal,
                       sort_order = excluded.sort_order""",
                (qid, label, kind, source, personal, order),
            )

        conn.execute("DELETE FROM documents")  # ลบลูกตาม ON DELETE CASCADE
        for title, citation, effective, chunks in DOCUMENTS:
            cur = conn.execute(
                """INSERT INTO documents (title, citation_label, effective_date, created_at)
                   VALUES (?, ?, ?, ?)""",
                (title, citation, effective, now),
            )
            doc_id = cur.lastrowid
            for ordinal, (page, content) in enumerate(chunks):
                conn.execute(
                    """INSERT INTO doc_chunks (document_id, ordinal, page, content)
                       VALUES (?, ?, ?, ?)""",
                    (doc_id, ordinal, page, content),
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="นำเข้าข้อมูลตั้งต้นของตู้บริการข้อมูล")
    parser.add_argument("--reset", action="store_true", help="ลบฐานข้อมูลเดิมแล้วสร้างใหม่")
    args = parser.parse_args(argv)

    if args.reset and config.DB_PATH.exists():
        config.DB_PATH.unlink()
        for suffix in ("-wal", "-shm"):
            extra = config.DB_PATH.with_name(config.DB_PATH.name + suffix)
            extra.unlink(missing_ok=True)
        print(f"ลบฐานข้อมูลเดิม: {config.DB_PATH}")

    conn = db_module.connect()
    db_module.init_db(conn)
    seed(conn)

    counts = {
        name: conn.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()["n"]
        for name in ("students", "courses", "rooms", "sections", "enrollments",
                     "exams", "announcements", "quick_questions", "doc_chunks")
    }
    conn.close()

    print(f"นำเข้าข้อมูลลง {config.DB_PATH} เรียบร้อย")
    for name, n in counts.items():
        print(f"  {name:18s} {n:4d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
