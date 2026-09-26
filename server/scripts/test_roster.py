"""ตรวจการอ่านและนำเข้ารายชื่อนักศึกษาจากระบบทะเบียน

    .venv/Scripts/python.exe scripts/test_roster.py

ใช้ไฟล์ RTF ที่สร้างขึ้นเองในหน่วยความจำ ไม่พึ่งไฟล์รายชื่อจริง
เพราะไฟล์รายชื่อเป็นข้อมูลส่วนบุคคลและไม่ได้อยู่ใน git
ถ้ามีไฟล์จริงอยู่ในเครื่อง จะตรวจเพิ่มให้ด้วยว่าอ่านได้ครบ
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db as db_module, repo, roster, thai  # noqa: E402

_results: list[tuple[bool, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((ok, name))
    print(f"  [{'ผ่าน' if ok else 'ไม่ผ่าน'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def make_rtf() -> bytes:
    """สร้างไฟล์ RTF แบบเดียวกับที่ระบบทะเบียนส่งออก (ภาษาไทย cp874)"""

    def thai(text: str) -> str:
        return "".join(
            ch if ord(ch) < 128 else f"\\'{ch.encode('cp874')[0]:02x}" for ch in text
        )

    rows = [
        (1, "6600000101", "นางสาวสมหญิง ตั้งใจเรียน", "10"),
        (2, "6600000102", "นายสมชาย ขยันมาก", "10"),
        (3, "6600000103", "นายลาออก ไปแล้ว", "50"),
        (4, "6600000104", "นางสาวพ้นสภาพ คะแนนน้อย", "61"),
        (5, "6600000105", "ไม่มีคำนำหน้า ชื่อนี้", "10"),
    ]

    parts = [
        r"{\rtf1\ansi\ansicpg874\uc1 \deff0",
        r"{\fonttbl{\f0\froman Times New Roman;}{\f15\froman Angsana New;}}",
        r"{\colortbl;\red0\green0\blue0;}",
        r"{\*\shppict picture-data-here}",
        thai("หลักสูตร   65304010  :  วิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์")
        + r"\cell "
        + thai("ปีการศึกษาที่เข้า   2566")
        + r"\row ",
        thai("คณะ   วิทยาศาสตร์") + r"\cell " + thai("ระดับการศึกษา   ปริญญาตรี  ปกติ") + r"\row ",
        thai("10 : กำลังศึกษา, 11 : รักษาสภาพ, 50 : ลาออก, 61 : พ้นสภาพข้อ 16.10.1, 72 : หมดสภาพ")
        + r"\par ",
        thai("เลขที่") + r"\cell " + thai("รหัสประจำตัว") + r"\cell "
        + thai("ชื่อ") + r"\cell " + thai("สถานภาพ") + r"\row ",
    ]
    for no, sid, name, status in rows:
        parts.append(
            f"{no}\\cell {sid}\\cell " + thai(name) + r"\cell " + status + r"\row "
        )
    parts.append("}")
    return "".join(parts).encode("latin-1")


def main() -> int:
    print("1. อ่านไฟล์ RTF ของระบบทะเบียน")
    tmp = Path(config.SERVER_DIR) / "data" / "_test_roster.rtf"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(make_rtf())
    try:
        data = roster.parse(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    check(data.program_code == "65304010", "อ่านรหัสหลักสูตรได้", str(data.program_code))
    check(data.entry_year == 2566, "อ่านปีการศึกษาที่เข้าได้", str(data.entry_year))
    check(data.faculty == "วิทยาศาสตร์", "อ่านชื่อคณะได้", str(data.faculty))
    check(len(data.students) == 5, "อ่านรายชื่อครบทุกแถว", f"{len(data.students)} คน")

    by_id = {s.student_id: s for s in data.students}
    check(by_id["6600000101"].prefix == "นางสาว"
          and by_id["6600000101"].name == "สมหญิง ตั้งใจเรียน",
          "แยกคำนำหน้าออกจากชื่อได้")
    check(by_id["6600000105"].prefix is None, "ชื่อที่ไม่มีคำนำหน้าไม่ถูกตัดผิด",
          by_id["6600000105"].name)
    check(by_id["6600000103"].status_label == "ลาออก", "แปลรหัสสถานภาพเป็นข้อความได้")

    print("\n2. สถานภาพกำหนดสิทธิใช้ตู้")
    check(by_id["6600000101"].active, "ผู้ที่กำลังศึกษาใช้ตู้ได้")
    check(not by_id["6600000103"].active, "ผู้ที่ลาออกใช้ตู้ไม่ได้")
    check(not by_id["6600000104"].active, "ผู้ที่พ้นสภาพใช้ตู้ไม่ได้")
    check(data.active_count == 3, "นับผู้ที่ใช้ตู้ได้ถูกต้อง", f"{data.active_count} คน")

    print("\n3. คำนวณชั้นปี")
    check(roster.study_year(2566, "2569-1") == 4, "เข้าปี 2566 ในปีการศึกษา 2569 = ชั้นปีที่ 4")
    check(roster.study_year(2569, "2569-1") == 1, "เข้าปีเดียวกัน = ชั้นปีที่ 1")
    check(roster.study_year(None, "2569-1") is None, "ไม่รู้ปีที่เข้า ก็ไม่เดาชั้นปี")
    check(roster.study_year(2550, "2569-1") is None, "ค่าที่เป็นไปไม่ได้ถูกตัดทิ้ง")

    print("\n4. นำเข้าฐานข้อมูล")
    conn = db_module.connect(Path(":memory:"))
    db_module.init_db(conn)
    now = thai.now().isoformat(timespec="seconds")
    year = roster.study_year(data.entry_year, "2569-1")

    with conn:
        results = [
            repo.upsert_roster_student(
                conn, student_id=s.student_id, prefix=s.prefix, name=s.name,
                year=year, entry_year=data.entry_year, program=data.program_name,
                program_code=data.program_code, status_code=s.status_code,
                status_label=s.status_label, active=s.active, now=now,
            )
            for s in data.students
        ]
    check(all(r == "added" for r in results), "เพิ่มนักศึกษาใหม่ทุกคน")

    with conn:
        again = repo.upsert_roster_student(
            conn, student_id="6600000101", prefix="นางสาว", name="สมหญิง เปลี่ยนนามสกุล",
            year=year, entry_year=2566, program=data.program_name,
            program_code=data.program_code, status_code="10", status_label="กำลังศึกษา",
            active=True, now=now,
        )
    check(again == "updated", "นำเข้าซ้ำถือเป็นการอัปเดต")
    check(repo.find_student_by_code(conn, "6600000101")["name"] == "สมหญิง เปลี่ยนนามสกุล",
          "ชื่อถูกอัปเดตตามไฟล์ล่าสุด")

    print("\n5. ตู้ต้องปฏิเสธผู้ที่ไม่ได้เป็นนักศึกษาแล้ว")
    check(repo.is_active(repo.find_student_by_code(conn, "6600000101")),
          "ผู้ที่กำลังศึกษาผ่านการตรวจ")
    left = repo.find_student_by_code(conn, "6600000103")
    check(not repo.is_active(left), "ผู้ที่ลาออกไม่ผ่านการตรวจ")
    check("ลาออก" in repo.status_message(left),
          "ข้อความอธิบายบอกสาเหตุจริง ไม่ใช่ข้อความกลาง ๆ", repo.status_message(left)[:50])
    check(not repo.is_active(None), "รหัสที่ไม่มีในระบบไม่ผ่านการตรวจ")

    # ข้อมูลเดิมที่ยังไม่รู้สถานภาพต้องใช้ตู้ได้ ไม่งั้นตู้จะหยุดทำงานหลังอัปเกรด
    with conn:
        conn.execute("UPDATE students SET active = 1, status_code = NULL WHERE student_id = ?",
                     ("6600000102",))
    check(repo.is_active(repo.find_student_by_code(conn, "6600000102")),
          "ข้อมูลเดิมที่ยังไม่รู้สถานภาพถือว่ายังศึกษาอยู่")

    conn.close()

    # ---- ถ้ามีไฟล์จริงในเครื่อง ตรวจเพิ่ม ----
    real = Path(config.SERVER_DIR) / "data" / "roster" / "studentByProgram_RTF.asp"
    if real.is_file():
        print("\n6. ไฟล์รายชื่อจริงในเครื่องนี้")
        live = roster.parse(real)
        check(len(live.students) > 0, "อ่านรายชื่อจริงได้", f"{len(live.students)} คน")
        check(not live.skipped, "ไม่มีแถวที่อ่านไม่ได้", f"{len(live.skipped)} รายการ")
        check(all(s.student_id.isdigit() for s in live.students),
              "รหัสนักศึกษาทุกคนเป็นตัวเลขล้วน")
        check(len({s.student_id for s in live.students}) == len(live.students),
              "ไม่มีรหัสซ้ำ")

    failed = [name for ok, name in _results if not ok]
    print(f"\n{'=' * 52}")
    print(f"ผ่าน {len(_results) - len(failed)}/{len(_results)} ข้อ")
    for name in failed:
        print(f"  ไม่ผ่าน: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
