"""จัดการทะเบียนนักศึกษาและข้อมูลใบหน้า — สำหรับเจ้าหน้าที่สำนักงานสาขา

    .venv/Scripts/python.exe scripts/students.py --list
    .venv/Scripts/python.exe scripts/students.py --registry
    .venv/Scripts/python.exe scripts/students.py --show 6604101388
    .venv/Scripts/python.exe scripts/students.py --export 6604101388 --out ของฉัน.json
    .venv/Scripts/python.exe scripts/students.py --forget 6604101388
    .venv/Scripts/python.exe scripts/students.py --cleanup-consents

ทำไมต้องมีเครื่องมือนี้
  การลบข้อมูลใบหน้าผ่านหน้าตู้ต้องยืนยันตัวตนด้วยใบหน้าก่อน
  ถ้าระบบจำหน้าเจ้าของข้อมูลไม่ได้ (เปลี่ยนทรงผม ใส่แว่น กล้องเสีย)
  เจ้าของข้อมูลจะลบข้อมูลตัวเองไม่ได้เลย ซึ่งขัดกับสิทธิที่กฎหมายรับรองไว้
  จึงต้องมีช่องทางให้เจ้าหน้าที่ดำเนินการแทนเมื่อเจ้าของข้อมูลมาติดต่อ

เครื่องมือนี้ตั้งใจให้รันบนเครื่องตู้โดยตรง (ผ่าน SSH) ไม่ได้เปิดเป็น API
เพราะยังไม่มีระบบยืนยันตัวตนของเจ้าหน้าที่ การเปิดเป็นเส้นทางเว็บโดยไม่มีการยืนยัน
จะกลายเป็นช่องให้ใครก็ได้ลบข้อมูลใบหน้าของผู้อื่น
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module, repo, thai  # noqa: E402


def cmd_list(conn) -> int:
    rows = conn.execute(
        """SELECT student_id, name, year, program, is_synthetic,
                  (SELECT COUNT(*) FROM face_embeddings f
                   JOIN consents c ON c.id = f.consent_id AND c.revoked_at IS NULL
                   WHERE f.student_id = students.id) AS faces
           FROM students ORDER BY student_id"""
    ).fetchall()

    if not rows:
        print("ยังไม่มีนักศึกษาในระบบ — นำเข้ารายชื่อด้วย scripts/import_students.py")
        return 0

    print(f"นักศึกษาในระบบ {len(rows)} คน\n")
    print(f"  {'รหัส':<12} {'ชื่อ':<26} {'ชั้นปี':<6} {'ใบหน้า':<8} หมายเหตุ")
    print(f"  {'-' * 12} {'-' * 26} {'-' * 6} {'-' * 8} {'-' * 20}")
    for r in rows:
        note = "ข้อมูลสมมติสำหรับสาธิต" if r["is_synthetic"] else ""
        face = "ลงทะเบียนแล้ว" if r["faces"] else "—"
        print(f"  {r['student_id']:<12} {r['name']:<26} {str(r['year'] or '-'):<6} {face:<8} {note}")
    return 0


def cmd_registry(conn) -> int:
    rows = repo.registration_registry(conn)
    print(f"ผู้ที่มีข้อมูลใบหน้าอยู่ในระบบ {len(rows)} คน\n")
    if not rows:
        print("  (ยังไม่มีใครลงทะเบียน)")
    for r in rows:
        mark = " · ข้อมูลสมมติ" if r["isSynthetic"] else ""
        print(f"  {r['studentId']}  {r['name']}{mark}")
        print(f"      ลงทะเบียนเมื่อ  {r['registeredAt'][:16].replace('T', ' ')}"
              f"  คุณภาพ {r['quality']:.3f}  โมเดล {r['model']}")
        print(f"      ความยินยอม     #{r['consentId']}"
              f"  {r['consentGrantedAt'][:16].replace('T', ' ')}"
              f"  ฉบับ {r['policyVersion']}  วิธี {r['consentMethod']}")

    orphans = repo.orphan_consents(conn)
    if orphans:
        print(f"\n  ⚠ ความยินยอมค้างอยู่ {len(orphans)} รายการ (ไม่มีข้อมูลใดผูกไว้)")
        for o in orphans:
            print(f"      #{o['id']} {o['studentId']} {o['name']} · {o['grantedAt'][:16].replace('T', ' ')}")
        print("      ล้างด้วย --cleanup-consents")
    return 0


def cmd_show(conn, code: str) -> int:
    record = repo.student_record(conn, code)
    if record is None:
        print(f"ไม่พบรหัสนักศึกษา {code}")
        return 1

    s = record["student"]
    print(f"ข้อมูลทั้งหมดที่ระบบเก็บไว้เกี่ยวกับ {s['name']} ({s['studentId']})\n")
    print(f"  ชั้นปี           {s['year'] or '-'}")
    print(f"  หลักสูตร         {s['program'] or '-'}")
    print(f"  อาจารย์ที่ปรึกษา  {s['advisor'] or '-'}")
    print(f"  รายวิชาที่ลงทะเบียน {record['enrolledCourses']} วิชา")
    if s["isSynthetic"]:
        print("  หมายเหตุ         เป็นข้อมูลสมมติสำหรับสาธิต")

    print(f"\n  ความยินยอม {len(record['consents'])} รายการ")
    for c in record["consents"]:
        state = f"ถอนแล้วเมื่อ {c['revokedAt'][:16].replace('T', ' ')}" if c["revokedAt"] else "ยังมีผล"
        print(f"    #{c['id']} {c['grantedAt'][:16].replace('T', ' ')} "
              f"ฉบับ {c['policyVersion']} วิธี {c['method']} — {state}")

    print(f"\n  ข้อมูลใบหน้า {len(record['faceEmbeddings'])} รายการ")
    for f in record["faceEmbeddings"]:
        print(f"    #{f['id']} {f['createdAt'][:16].replace('T', ' ')} "
              f"{f['dimensions']} มิติ โมเดล {f['model']} คุณภาพ {f['quality']:.3f}")
    if record["faceEmbeddings"]:
        print("    เก็บเป็นค่าเวกเตอร์เท่านั้น ไม่มีภาพใบหน้า และย้อนกลับเป็นภาพไม่ได้")
    return 0


def cmd_export(conn, code: str, out: Path | None) -> int:
    record = repo.student_record(conn, code)
    if record is None:
        print(f"ไม่พบรหัสนักศึกษา {code}")
        return 1

    text = json.dumps(record, ensure_ascii=False, indent=2)
    if out is None:
        print(text)
    else:
        out.write_text(text, encoding="utf-8")
        print(f"บันทึกข้อมูลของ {record['student']['name']} ลง {out}")
    return 0


def cmd_forget(conn, code: str, assume_yes: bool) -> int:
    record = repo.student_record(conn, code)
    if record is None:
        print(f"ไม่พบรหัสนักศึกษา {code}")
        return 1

    s = record["student"]
    live = [c for c in record["consents"] if c["revokedAt"] is None]
    print(f"กำลังจะลบข้อมูลใบหน้าของ {s['name']} ({s['studentId']})")
    print(f"  เวกเตอร์ใบหน้า   {len(record['faceEmbeddings'])} รายการ — ลบทิ้งถาวร")
    print(f"  ความยินยอม      {len(live)} รายการที่ยังมีผล — บันทึกเวลาถอนไว้เป็นหลักฐาน")
    print("  ตารางเรียนและข้อมูลนักศึกษาไม่ถูกลบ")

    if not record["faceEmbeddings"] and not live:
        print("\nไม่มีอะไรต้องลบ")
        return 0

    if not assume_yes:
        try:
            answer = input("\nยืนยันหรือไม่ (พิมพ์ ใช่ เพื่อดำเนินการ): ").strip()
        except EOFError:
            print("\nยกเลิก — ต้องยืนยันผ่านแป้นพิมพ์ หรือใส่ --yes")
            return 1
        if answer not in {"ใช่", "yes", "y"}:
            print("ยกเลิก")
            return 1

    result = repo.forget_student(conn, code, thai.now().isoformat(timespec="seconds"))
    print(f"\nลบเรียบร้อย — เวกเตอร์ {result['vectorsDeleted']} รายการ "
          f"· ถอนความยินยอม {result['consentsRevoked']} รายการ")
    print(f"เวลาที่ดำเนินการ {result['at']}")
    return 0


def cmd_cleanup(conn) -> int:
    orphans = repo.orphan_consents(conn)
    if not orphans:
        print("ไม่มีความยินยอมค้าง")
        return 0
    print(f"พบความยินยอมค้าง {len(orphans)} รายการ (ยินยอมแล้วแต่ไม่ได้ถ่ายใบหน้าจนจบ)")
    for o in orphans:
        print(f"  #{o['id']} {o['studentId']} {o['name']} · {o['grantedAt'][:16].replace('T', ' ')}")
    count = repo.clear_orphan_consents(conn, thai.now().isoformat(timespec="seconds"))
    print(f"\nถอนความยินยอมที่ค้างอยู่ {count} รายการแล้ว")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="จัดการทะเบียนนักศึกษาและข้อมูลใบหน้า",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="รายชื่อนักศึกษาทั้งหมด")
    group.add_argument("--registry", action="store_true", help="ผู้ที่ลงทะเบียนใบหน้าแล้ว")
    group.add_argument("--show", metavar="รหัส", help="ข้อมูลทั้งหมดของคนหนึ่งคน")
    group.add_argument("--export", metavar="รหัส", help="ส่งออกข้อมูลของคนหนึ่งคนเป็น JSON")
    group.add_argument("--forget", metavar="รหัส", help="ลบข้อมูลใบหน้าและถอนความยินยอม")
    group.add_argument("--cleanup-consents", action="store_true",
                       help="ถอนความยินยอมที่ค้างโดยไม่มีข้อมูลผูกไว้")
    parser.add_argument("--out", type=Path, help="ไฟล์ปลายทางของ --export")
    parser.add_argument("--yes", action="store_true", help="ไม่ต้องถามยืนยัน")
    args = parser.parse_args()

    conn = db_module.connect()
    try:
        if args.list:
            return cmd_list(conn)
        if args.registry:
            return cmd_registry(conn)
        if args.show:
            return cmd_show(conn, args.show)
        if args.export:
            return cmd_export(conn, args.export, args.out)
        if args.forget:
            return cmd_forget(conn, args.forget, args.yes)
        return cmd_cleanup(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
