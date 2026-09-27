"""นำเข้าตารางเรียนจริงรายบุคคลจากระบบทะเบียน

    .venv/Scripts/python.exe scripts/import_my_semester.py ../csmju_dataset/my_semester_1-2569
    .venv/Scripts/python.exe scripts/import_my_semester.py <โฟลเดอร์> --dry-run

ทำไมเรื่องนี้สำคัญ
  ตั้งแต่เริ่มโครงงาน ตารางเรียนบนหน้าจอเป็นข้อมูลสมมติมาตลอด
  เพราะสาขายังไม่มีช่องทางส่งตารางเรียนจริงมาให้
  หน้าจอจึงต้องติดป้ายเตือนไว้ว่า "ตารางเรียนเป็นข้อมูลตัวอย่าง"
  ไฟล์นี้คือของจริงไฟล์แรก ที่นักศึกษาดึงมาจากระบบทะเบียนของตัวเอง

ทำไมต้องรันด้วยมือ ไม่ใช่เส้นทาง API
  ไฟล์นี้เป็นข้อมูลของนักศึกษาที่ระบุตัวตนได้จริง บอกได้ว่าเจ้าตัว
  อยู่ที่ไหนในแต่ละวันเวลา ซึ่งเป็นข้อมูลที่อ่อนไหวกว่าตารางเรียนทั่วไป
  ระบบยังไม่มีการยืนยันตัวตนของเจ้าหน้าที่ การเปิดเป็นเส้นทาง API
  จึงเท่ากับให้ใครก็ได้เขียนทับตารางเรียนของคนอื่น
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module, repo, thai  # noqa: E402

# ชื่อวันในไฟล์ → เลขวันแบบ ISO ที่ฐานข้อมูลใช้ (1 = จันทร์)
DAYS = {"จันทร์": 1, "อังคาร": 2, "พุธ": 3, "พฤหัสบดี": 4, "พฤหัสบดี ": 4,
        "ศุกร์": 5, "เสาร์": 6, "อาทิตย์": 7}

# ชื่อห้องในระบบทะเบียน → ชื่อย่อที่ฐานข้อมูลของตู้ใช้อยู่
# ระบบทะเบียนกับเว็บไซต์สาขาเรียกห้องเดียวกันคนละชื่อ
# ถ้าไม่แมปไว้ ตู้จะสร้างห้องซ้ำขึ้นมาใหม่ แล้วบอกชั้นกับอาคารไม่ได้
ROOM_ALIASES = {
    "lab คอม 5": "Labcom 5",
    "lab คอม 1": "Lab 1",
    "lab คอม 2": "Lab 2",
    "lab คอม 3": "Lab 3",
    "lab คอม 4": "Lab 4",
    "บรรยาย คอม 8": "Lect 8",
    "บรรยาย คอม 6": "Lect 6",
    "lab network": "Lab Network",
}

EXAM_TYPES = {"กลางภาค": "สอบกลางภาค", "ปลายภาค": "สอบปลายภาค"}


def find_room(conn, name: str | None, *, create: bool = False) -> int | None:
    """หา room_id จากชื่อที่ระบบทะเบียนใช้

    ห้องของคณะอื่นไม่มีในฐานข้อมูลของสาขา เพราะสาขาเก็บเฉพาะห้องของตัวเอง
    แต่นักศึกษายังต้องรู้ว่าเรียนห้องอะไร จึงสร้างห้องไว้เท่าที่รู้จริง
    คือมีแค่ชื่อห้อง ไม่มีชั้นและอาคาร แล้วให้หน้าจอไม่แสดงสองอย่างนั้น
    ดีกว่าเดาชั้นขึ้นมาเอง ซึ่งจะทำให้นักศึกษาเดินขึ้นผิดชั้น
    """
    if not name:
        return None
    key = name.strip().lower()
    short = ROOM_ALIASES.get(key)
    if short:
        row = conn.execute("SELECT id FROM rooms WHERE short_name = ?", (short,)).fetchone()
        if row:
            return row["id"]

    bare = name.strip()
    row = conn.execute(
        "SELECT id FROM rooms WHERE short_name = ? OR name = ? OR name LIKE ?",
        (bare, bare, f"%{bare}%"),
    ).fetchone()
    if row:
        return row["id"]

    if not create:
        return None

    # ไม่ใส่ building_id และ floor เพราะไม่รู้จริง
    cur = conn.execute(
        "INSERT INTO rooms (code, name, short_name) VALUES (?, ?, ?)",
        (f"ext:{bare}", bare, bare),
    )
    return cur.lastrowid


def upsert_course(conn, code: str, title: str | None, credits: Any) -> int:
    row = conn.execute("SELECT id, name FROM courses WHERE code = ?", (code,)).fetchone()
    if row is not None:
        # ชุดข้อมูลของสาขามีบางวิชาที่ชื่อยังเป็นตัวยึดตำแหน่ง เช่น 'Course 10301366'
        # ไฟล์จากระบบทะเบียนมีชื่อจริง จึงถือว่าใหม่กว่าและเขียนทับได้
        if title and (not row["name"] or row["name"].startswith("Course ")):
            conn.execute("UPDATE courses SET name = ? WHERE id = ?", (title, row["id"]))
        return row["id"]

    cur = conn.execute(
        "INSERT INTO courses (code, name, credits) VALUES (?, ?, ?)",
        (code, title or code, credits),
    )
    return cur.lastrowid


def main() -> int:
    parser = argparse.ArgumentParser(description="นำเข้าตารางเรียนจริงรายบุคคล")
    parser.add_argument("folder", type=Path, help="โฟลเดอร์ my_semester_*")
    parser.add_argument("--dry-run", action="store_true", help="แสดงผลอย่างเดียว ไม่บันทึก")
    args = parser.parse_args()

    source = args.folder / f"{args.folder.name}.json"
    if not source.is_file():
        matches = list(args.folder.glob("my_semester_*.json"))
        if not matches:
            print(f"ไม่พบไฟล์ my_semester_*.json ใน {args.folder}")
            return 2
        source = matches[0]

    data = json.loads(source.read_text(encoding="utf-8"))
    student = data["student"]
    code = str(student["student_id"]).strip()

    conn = db_module.connect()
    db_module.init_db(conn)

    row = repo.find_student_by_code(conn, code)
    if row is None:
        print(f"ไม่พบนักศึกษารหัส {code} ในระบบ — นำเข้ารายชื่อก่อนแล้วลองใหม่")
        return 1
    student_pk = row["id"]

    term = repo.get_current_term(conn)
    if term is None:
        print("ไม่พบภาคการศึกษาปัจจุบันในระบบ")
        return 1

    print(f"นักศึกษา {row['name']} ({code})")
    print(f"ภาคการศึกษา {term['code']}")
    print(f"ที่ปรึกษา {student.get('advisor') or '—'}")
    print()

    sessions = data.get("my_class_sessions") or []
    courses = {c["course_code"]: c for c in (data.get("registered_courses") or [])}

    print(f"ตารางเรียน {len(sessions)} คาบ")
    unknown_rooms: list[str] = []
    for s in sessions:
        room_id = find_room(conn, s.get("room"))
        if room_id is None and s.get("room"):
            unknown_rooms.append(s["room"])
        mark = " " if room_id else "?"
        print(f" {mark} {s['day_th']:<9} {s['start']}-{s['end']}  {s['course_code']} "
              f"{s['title_th'][:30]:<32} {s.get('room') or '—'}")

    exams = data.get("my_exams") or []
    print(f"\nกำหนดสอบ {len(exams)} รายการ")
    for e in exams:
        print(f"   {e['exam_type']:<10} {e['date_th']} {e['time']}  "
              f"{e['course_code']} ห้อง {e.get('room') or '—'}")

    if unknown_rooms:
        print(f"\nห้องนอกสาขา: {', '.join(sorted(set(unknown_rooms)))}")
        print("  จะบันทึกชื่อห้องไว้ แต่ไม่มีข้อมูลชั้นและอาคารเพราะไม่รู้จริง")
        print("  หน้าจอจะแสดงเฉพาะชื่อห้อง ไม่เดาชั้นขึ้นมาเอง")

    if args.dry_run:
        print("\n(โหมดทดลอง ไม่ได้บันทึกอะไร)")
        conn.close()
        return 0

    now = thai.now().isoformat(timespec="seconds")
    with db_module.transaction(conn):
        # ลบตารางเดิมของนักศึกษาคนนี้ก่อน กันข้อมูลเก่าค้างเมื่อระบบทะเบียนแก้ไข
        # ลบเฉพาะการลงทะเบียนของคนนี้ ไม่แตะ sections ที่คนอื่นอาจใช้ร่วมกัน
        conn.execute("DELETE FROM enrollments WHERE student_id = ?", (student_pk,))

        for s in sessions:
            day = DAYS.get((s.get("day_th") or "").strip())
            if day is None:
                continue
            course_code = s["course_code"]
            meta = courses.get(course_code, {})
            course_id = upsert_course(conn, course_code, s.get("title_th"),
                                      meta.get("credits"))
            room_id = find_room(conn, s.get("room"), create=True)

            existing = conn.execute(
                """SELECT id FROM sections
                   WHERE term_id = ? AND course_id = ? AND day = ? AND start_time = ?""",
                (term["id"], course_id, day, s["start"]),
            ).fetchone()

            if existing:
                section_id = existing["id"]
                conn.execute(
                    """UPDATE sections SET end_time = ?, room_id = ?, teacher = ?,
                                           is_synthetic = 0
                       WHERE id = ?""",
                    (s["end"], room_id, s.get("instructor"), section_id),
                )
            else:
                cur = conn.execute(
                    """INSERT INTO sections
                           (term_id, course_id, room_id, day, start_time, end_time,
                            teacher, is_synthetic)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                    (term["id"], course_id, room_id, day, s["start"], s["end"],
                     s.get("instructor")),
                )
                section_id = cur.lastrowid

            conn.execute(
                "INSERT OR IGNORE INTO enrollments (student_id, section_id) VALUES (?, ?)",
                (student_pk, section_id),
            )

        for e in exams:
            exam_type = EXAM_TYPES.get((e.get("exam_type") or "").strip())
            if not exam_type or not e.get("date_ce"):
                continue
            course_id = upsert_course(conn, e["course_code"], e.get("title_th"), None)
            times = (e.get("time") or "").split("-")
            conn.execute(
                """INSERT INTO exams
                       (term_id, course_id, room_id, exam_type, exam_date,
                        start_time, end_time, is_synthetic)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                   ON CONFLICT (term_id, course_id, exam_type) DO UPDATE SET
                       exam_date = excluded.exam_date,
                       start_time = excluded.start_time,
                       end_time = excluded.end_time,
                       room_id = excluded.room_id,
                       is_synthetic = 0""",
                (term["id"], course_id, find_room(conn, e.get("room"), create=True),
                 exam_type,
                 e["date_ce"],
                 times[0].strip() if times else "00:00",
                 times[1].strip() if len(times) > 1 else "00:00"),
            )

        advisor = student.get("advisor")
        if advisor:
            conn.execute(
                "UPDATE students SET advisor = ?, updated_at = ? WHERE id = ?",
                (advisor, now, student_pk),
            )

    total = conn.execute(
        "SELECT COUNT(*) n FROM enrollments WHERE student_id = ?", (student_pk,)
    ).fetchone()["n"]
    print(f"\nบันทึกแล้ว — {row['name']} มี {total} คาบเรียนจริงในระบบ")
    print("ตารางเรียนของนักศึกษาคนนี้ไม่ใช่ข้อมูลสมมติอีกต่อไป")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
