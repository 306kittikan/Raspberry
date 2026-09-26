"""นำเข้ารายชื่อนักศึกษาจากไฟล์ CSV ของสาขา

    .venv/Scripts/python.exe scripts/import_students.py รายชื่อ.csv
    .venv/Scripts/python.exe scripts/import_students.py รายชื่อ.csv --dry-run
    .venv/Scripts/python.exe scripts/import_students.py --template ตัวอย่าง.csv

ทำไมต้องมี: นักศึกษาจะลงทะเบียนใบหน้าได้ก็ต่อเมื่อรหัสของตนอยู่ในระบบแล้ว
ตู้จึงไม่รับสมัครคนใหม่เอง เพราะการกรอกรหัสที่หน้าตู้ไม่ได้ยืนยันว่าเป็นเจ้าของรหัสจริง
ถ้าปล่อยให้สร้างรายชื่อได้เอง ใครก็จองรหัสของผู้อื่นไว้ล่วงหน้าได้

รูปแบบไฟล์ (UTF-8, มีบรรทัดหัวตาราง)

    student_id,name,year,program,advisor
    6604101001,สมชาย ใจดี,3,วิทยาการคอมพิวเตอร์,ผศ.ดร.พาสน์ ปราโมกข์ชน

    student_id  จำเป็น · ตัวเลข 10 หลัก
    name        จำเป็น
    year        ไม่บังคับ
    program     ไม่บังคับ
    advisor     ไม่บังคับ

สคริปต์นี้ไม่ลบใครออกจากระบบ เพราะการลบนักศึกษาจะลบเวกเตอร์ใบหน้าตามไปด้วย
ซึ่งต้องเป็นการตัดสินใจของคน ไม่ใช่ผลข้างเคียงของการนำเข้าไฟล์
(ต้องการลบข้อมูลใบหน้าของใคร ใช้ scripts/students.py --forget)
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module, repo, thai  # noqa: E402

REQUIRED = ("student_id", "name")
STUDENT_ID = re.compile(r"^\d{8,12}$")

TEMPLATE = """student_id,name,year,program,advisor
6604101001,สมชาย ใจดี,3,วิทยาการคอมพิวเตอร์,ผศ.ดร.พาสน์ ปราโมกข์ชน
6604101002,สมหญิง รักเรียน,3,วิทยาการคอมพิวเตอร์,ผศ.ภานุวัฒน์ เมฆะ
"""


def read_rows(path: Path) -> tuple[list[dict], list[str], list[str]]:
    """อ่านไฟล์แล้วคืน (แถวที่ใช้ได้, บรรทัดที่ข้าม, คำเตือน)

    แยก "ข้าม" กับ "เตือน" ออกจากกัน เพราะความหมายต่างกันมาก
      ข้าม  = นำเข้าคนนี้ไม่ได้เลย (รหัสผิดรูปแบบ ไม่มีชื่อ หรือซ้ำ)
      เตือน = นำเข้าได้ แต่บางช่องใช้ไม่ได้ จึงปล่อยว่างไว้
    ถ้ารวมเป็นกองเดียว เจ้าหน้าที่จะไม่รู้ว่ามีใครตกหล่นไปหรือไม่
    """
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"ไฟล์ขาดคอลัมน์ {', '.join(missing)} — คอลัมน์ที่พบ: "
                f"{', '.join(reader.fieldnames or ['(ว่าง)'])}"
            )

        rows: list[dict] = []
        skipped: list[str] = []
        warnings: list[str] = []
        seen: set[str] = set()

        for line_no, raw in enumerate(reader, start=2):
            code = (raw.get("student_id") or "").strip()
            name = (raw.get("name") or "").strip()

            if not code and not name:
                continue  # บรรทัดว่าง
            if not STUDENT_ID.match(code):
                skipped.append(f"บรรทัด {line_no}: รหัสนักศึกษา '{code}' ไม่ถูกต้อง")
                continue
            if not name:
                skipped.append(f"บรรทัด {line_no}: ไม่มีชื่อของรหัส {code}")
                continue
            if code in seen:
                skipped.append(f"บรรทัด {line_no}: รหัส {code} ซ้ำในไฟล์ ใช้แถวแรก")
                continue

            year_raw = (raw.get("year") or "").strip()
            year = None
            if year_raw:
                if year_raw.isdigit():
                    year = int(year_raw)
                else:
                    warnings.append(
                        f"บรรทัด {line_no}: ชั้นปี '{year_raw}' ไม่ใช่ตัวเลข "
                        f"นำเข้า {code} โดยเว้นชั้นปีว่างไว้"
                    )

            seen.add(code)
            rows.append({
                "student_id": code,
                "name": name,
                "year": year,
                "program": (raw.get("program") or "").strip() or None,
                "advisor": (raw.get("advisor") or "").strip() or None,
            })

    return rows, skipped, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="นำเข้ารายชื่อนักศึกษาจากไฟล์ CSV")
    parser.add_argument("csv_file", nargs="?", type=Path, help="ไฟล์รายชื่อ")
    parser.add_argument("--dry-run", action="store_true", help="ตรวจไฟล์อย่างเดียว ไม่บันทึก")
    parser.add_argument("--template", type=Path, metavar="ไฟล์",
                        help="สร้างไฟล์ตัวอย่างแล้วจบ")
    args = parser.parse_args()

    if args.template:
        args.template.write_text(TEMPLATE, encoding="utf-8")
        print(f"สร้างไฟล์ตัวอย่างที่ {args.template}")
        return 0

    if args.csv_file is None:
        parser.error("ต้องระบุไฟล์ CSV หรือใช้ --template")
    if not args.csv_file.is_file():
        print(f"ไม่พบไฟล์ {args.csv_file}")
        return 1

    try:
        rows, skipped, warnings = read_rows(args.csv_file)
    except ValueError as exc:
        print(exc)
        return 1

    def report(title: str, items: list[str]) -> None:
        if not items:
            return
        print(f"{title} {len(items)} บรรทัด")
        for item in items[:20]:
            print(f"  {item}")
        if len(items) > 20:
            print(f"  … และอีก {len(items) - 20} บรรทัด")
        print()

    report("ข้ามไป", skipped)
    report("คำเตือน", warnings)

    if not rows:
        print("ไม่มีแถวที่นำเข้าได้")
        return 1

    print(f"แถวที่นำเข้าได้ {len(rows)} คน")
    if args.dry_run:
        for r in rows[:10]:
            print(f"  {r['student_id']}  {r['name']}  ชั้นปี {r['year'] or '-'}")
        if len(rows) > 10:
            print(f"  … และอีก {len(rows) - 10} คน")
        print("\n(--dry-run: ไม่ได้บันทึกอะไรลงฐานข้อมูล)")
        return 0

    conn = db_module.connect()
    db_module.init_db(conn)
    now = thai.now().isoformat(timespec="seconds")

    added = updated = 0
    try:
        with db_module.transaction(conn):
            for r in rows:
                result = repo.upsert_student(conn, now=now, **r)
                if result == "added":
                    added += 1
                else:
                    updated += 1
    finally:
        conn.close()

    print(f"\nเพิ่มใหม่ {added} คน · อัปเดต {updated} คน")
    print("ไม่มีใครถูกลบออกจากระบบ")
    if skipped:
        print(f"ข้ามไป {len(skipped)} บรรทัดที่นำเข้าไม่ได้")
    return 0


if __name__ == "__main__":
    sys.exit(main())
