"""นำเข้าตารางเรียนทั้งภาคการศึกษาจากระบบทะเบียน

    .venv/Scripts/python.exe scripts/import_timetable.py ../csmju_dataset/csmju_timetable_dataset

ชุดข้อมูลนี้ทำให้ตู้ตอบคำถามที่เดิมตอบไม่ได้เลยสองเรื่อง

  "ตอนนี้ห้องไหนว่าง"      นักศึกษาหาที่นั่งทำงานระหว่างคาบ
  "อาจารย์คนนี้ว่างไหม"     นักศึกษาจะไปพบอาจารย์แต่ไม่รู้ว่าติดสอนอยู่ไหม

ทั้งสองอย่างเป็นข้อมูลสาธารณะที่ไม่ผูกกับตัวบุคคล จึงเปิดดูได้โดยไม่ต้องยืนยันตัวตน
และตอบจากฐานข้อมูลในเครื่อง จึงใช้งานได้แม้ตู้ออฟไลน์
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module  # noqa: E402

DAYS = {"จันทร์": 1, "อังคาร": 2, "พุธ": 3, "พฤหัสบดี": 4,
        "ศุกร์": 5, "เสาร์": 6, "อาทิตย์": 7}

KIND = {"C": "บรรยาย", "L": "ปฏิบัติ", "R": "ประชุม", "S": "ศึกษาด้วยตนเอง", "T": "ติว"}


def main() -> int:
    parser = argparse.ArgumentParser(description="นำเข้าตารางเรียนทั้งภาคการศึกษา")
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()

    matches = list(args.folder.glob("timetable_*.json"))
    if not matches:
        print(f"ไม่พบไฟล์ timetable_*.json ใน {args.folder}")
        return 2
    data = json.loads(matches[0].read_text(encoding="utf-8"))

    conn = db_module.connect()
    db_module.init_db(conn)
    term = data.get("term", {})

    with db_module.transaction(conn):
        conn.execute("DELETE FROM campus_buildings")
        for b in data.get("buildings", []):
            conn.execute(
                "INSERT OR REPLACE INTO campus_buildings (code, name, campus) VALUES (?,?,?)",
                (b["building_code"], b["building_name"], b.get("campus")),
            )

        conn.execute("DELETE FROM class_sessions")
        skipped = 0
        for s in data.get("sessions", []):
            day = DAYS.get((s.get("day_th") or "").strip())
            # บางคาบในระบบทะเบียนไม่มีวันหรือเวลากำกับ เช่น วิชาที่นัดหมายกันเอง
            # ข้ามไปดีกว่าเดาวันให้ เพราะจะทำให้ "ห้องว่างไหม" ตอบผิด
            if day is None or not s.get("start") or not s.get("end"):
                skipped += 1
                continue
            if s["start"] >= s["end"]:
                skipped += 1
                continue
            conn.execute(
                """INSERT INTO class_sessions
                       (acadyear_be, semester, day, start_time, end_time, course_code,
                        course_title, section, kind, room, building_code, building_name,
                        instructors, is_cs)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (s.get("acadyear_be"), s.get("semester"), day, s["start"], s["end"],
                 s.get("course_code"), s.get("title_th"), s.get("section"),
                 KIND.get(s.get("type"), s.get("type_th")), s.get("room"),
                 s.get("building_code"), s.get("building_name"),
                 s.get("instructors"), int(bool(s.get("is_cs_department_course")))),
            )

        conn.execute("DELETE FROM cohort_sessions")
        for c in data.get("cohort_timetable", []):
            day = DAYS.get((c.get("day_th") or "").strip())
            if day is None:
                continue
            conn.execute(
                """INSERT INTO cohort_sessions
                       (year_level, entry_code, day, start_time, end_time, course_code,
                        course_title, section, room, building_code, instructors)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (c["year_level"], c.get("entry_code"), day, c["start"], c["end"],
                 c.get("course_code"), c.get("title_th"), c.get("section"),
                 c.get("room"), c.get("building_code"), c.get("instructors")),
            )

    n = lambda t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]  # noqa: E731
    print(f"ภาคการศึกษา {term.get('acadyear_be')}/{term.get('semester')}")
    print(f"  คาบเรียนทั้งหมด   {n('class_sessions'):5d}" + (f"  (ข้ามไป {skipped} คาบที่ไม่มีวันหรือเวลา)" if skipped else ""))
    print(f"  อาคาร             {n('campus_buildings'):5d}")
    print(f"  ตารางตามแผน       {n('cohort_sessions'):5d}")
    rooms = conn.execute("SELECT COUNT(DISTINCT room) c FROM class_sessions").fetchone()["c"]
    teachers = conn.execute(
        "SELECT COUNT(DISTINCT instructors) c FROM class_sessions WHERE instructors IS NOT NULL"
    ).fetchone()["c"]
    print(f"  ห้องที่มีการใช้งาน {rooms:5d}")
    print(f"  ผู้สอน             {teachers:5d}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
