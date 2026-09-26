"""นำเข้ารายชื่อนักศึกษาจากไฟล์รายงานของระบบทะเบียนมหาวิทยาลัย

    .venv/Scripts/python.exe scripts/import_roster.py data/roster/studentByProgram_RTF.asp --dry-run
    .venv/Scripts/python.exe scripts/import_roster.py data/roster/studentByProgram_RTF.asp

ไฟล์ต้นทางคือรายงาน "รายชื่อนักศึกษาตามหลักสูตร" ที่ส่งออกเป็น RTF
(นามสกุลไฟล์เป็น .asp แต่เนื้อในเป็น RTF เข้ารหัสภาษาไทยแบบ cp874)

ไฟล์รายชื่อเป็นข้อมูลส่วนบุคคลจริง เก็บไว้ใน server/data/roster/ ซึ่งถูกกันไม่ให้ขึ้น git
และสคริปต์นี้ไม่ส่งข้อมูลออกนอกเครื่องเลย

สถานภาพนักศึกษาถูกนำเข้าด้วย ผู้ที่ลาออกหรือพ้นสภาพจะถูกตั้ง active = 0
ตู้จะปฏิเสธไม่ให้คนกลุ่มนี้เข้าใช้งาน เพราะไม่ได้เป็นนักศึกษาของสาขาแล้ว
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module, repo, roster as roster_mod, thai  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="นำเข้ารายชื่อนักศึกษาจากไฟล์รายงานของระบบทะเบียน"
    )
    parser.add_argument("roster_file", type=Path, help="ไฟล์รายงาน (.asp / .rtf)")
    parser.add_argument("--dry-run", action="store_true", help="ตรวจไฟล์อย่างเดียว ไม่บันทึก")
    parser.add_argument(
        "--replace-demo",
        action="store_true",
        help="ยอมให้ทับข้อมูลนักศึกษาสาธิตที่มีข้อมูลใบหน้าอยู่ (ลบใบหน้านั้นทิ้ง)",
    )
    args = parser.parse_args()

    if not args.roster_file.is_file():
        print(f"ไม่พบไฟล์ {args.roster_file}")
        return 1

    data = roster_mod.parse(args.roster_file)
    if not data.students:
        print("อ่านไฟล์แล้วไม่พบรายชื่อนักศึกษา — รูปแบบไฟล์อาจไม่ใช่ที่รองรับ")
        return 1

    conn = db_module.connect()
    db_module.init_db(conn)
    term = repo.get_current_term(conn)
    year = roster_mod.study_year(data.entry_year, term["code"] if term else None)

    print(f"หลักสูตร    {data.program_code} : {data.program_name}")
    print(f"คณะ         {data.faculty}")
    print(f"ปีที่เข้า    {data.entry_year}" + (f"  → ชั้นปีที่ {year}" if year else ""))
    print(f"นักศึกษา     {len(data.students)} คน "
          f"(ยังศึกษาอยู่ {data.active_count} · ไม่ใช้ตู้แล้ว {len(data.students) - data.active_count})")
    if data.skipped:
        print(f"ข้ามไป      {len(data.skipped)} รายการ")
        for item in data.skipped:
            print(f"   {item}")

    # ---- ตรวจการชนกับข้อมูลสาธิตที่มีข้อมูลใบหน้าอยู่ ----
    # ถ้านักศึกษาสาธิตที่เคยลงทะเบียนใบหน้าไว้ ถูกทับด้วยคนจริงที่ใช้รหัสเดียวกัน
    # ใบหน้าที่เก็บไว้จะกลายเป็นของคนจริงคนนั้นทันที ทั้งที่ไม่ใช่ใบหน้าของเขา
    incoming = {s.student_id for s in data.students}
    conflicts = [
        r for r in conn.execute(
            """SELECT s.student_id, s.name FROM students s
               WHERE s.is_synthetic = 1
                 AND EXISTS (SELECT 1 FROM face_embeddings f
                             JOIN consents c ON c.id = f.consent_id AND c.revoked_at IS NULL
                             WHERE f.student_id = s.id)"""
        ).fetchall()
        if r["student_id"] in incoming
    ]

    if conflicts and not args.replace_demo:
        print("\n⚠ หยุดการนำเข้า — พบข้อมูลใบหน้าที่ผูกกับนักศึกษาสาธิต")
        for c in conflicts:
            real = next(s for s in data.students if s.student_id == c["student_id"])
            print(f"   {c['student_id']}  สาธิต '{c['name']}'  →  จริง '{real.name}'")
        print("\nถ้านำเข้าทับ ใบหน้าที่เก็บไว้จะกลายเป็นของนักศึกษาจริงคนนั้นทันที")
        print("ทั้งที่ไม่ใช่ใบหน้าของเขา ซึ่งทำให้ระบบทักผิดคนและเปิดเผยข้อมูลผิดตัว")
        print("\nเลือกทางใดทางหนึ่งก่อน")
        for c in conflicts:
            print(f"   .venv/Scripts/python.exe scripts/students.py --forget {c['student_id']}")
        print("   หรือสั่งนำเข้าอีกครั้งด้วย --replace-demo เพื่อให้ลบใบหน้าเหล่านั้นให้อัตโนมัติ")
        conn.close()
        return 1

    if args.dry_run:
        print("\nตัวอย่าง 5 คนแรก")
        for s in data.students[:5]:
            mark = "" if s.active else f"  (ไม่ใช้ตู้: {s.status_label or s.status_code})"
            print(f"   {s.student_id}  {s.prefix or '':8s}{s.name}{mark}")
        print("\n(--dry-run: ไม่ได้บันทึกอะไรลงฐานข้อมูล)")
        conn.close()
        return 0

    now = thai.now().isoformat(timespec="seconds")

    removed_faces = 0
    if conflicts:
        for c in conflicts:
            result = repo.forget_student(conn, c["student_id"], now)
            removed_faces += result["vectorsDeleted"] if result else 0
        print(f"\nลบข้อมูลใบหน้าของนักศึกษาสาธิต {removed_faces} รายการก่อนนำเข้า")

    added = updated = 0
    with db_module.transaction(conn):
        for s in data.students:
            result = repo.upsert_roster_student(
                conn,
                student_id=s.student_id,
                prefix=s.prefix,
                name=s.name,
                year=year,
                entry_year=data.entry_year,
                program=data.program_name,
                program_code=data.program_code,
                status_code=s.status_code,
                status_label=s.status_label,
                active=s.active,
                now=now,
            )
            if result == "added":
                added += 1
            else:
                updated += 1

    remaining_demo = conn.execute(
        "SELECT COUNT(*) c FROM students WHERE is_synthetic = 1"
    ).fetchone()["c"]
    conn.close()

    print(f"\nเพิ่มใหม่ {added} คน · อัปเดต {updated} คน")
    print(f"ในจำนวนนี้ใช้ตู้ได้ {data.active_count} คน")
    print("ไม่มีใครถูกลบออกจากระบบ")
    if remaining_demo:
        print(f"\nยังมีนักศึกษาสาธิตเหลืออยู่ {remaining_demo} คน")
        print("ลบได้ด้วย .venv/Scripts/python.exe -m app.seed --real-only --reset")
        print("(คำสั่งนั้นจะล้างข้อมูลใบหน้าทั้งหมดด้วย)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
