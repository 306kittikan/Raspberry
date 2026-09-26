"""ตรวจทะเบียนนักศึกษาและสิทธิของเจ้าของข้อมูล

    .venv/Scripts/python.exe scripts/test_registry.py

ทำงานบนฐานข้อมูลชั่วคราวในหน่วยความจำ ไม่แตะฐานข้อมูลจริงของตู้
จึงรันซ้ำได้ตลอดโดยไม่กระทบข้อมูลใครทั้งสิ้น
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module, repo, thai  # noqa: E402
from app.services import face  # noqa: E402

_results: list[tuple[bool, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((ok, name))
    print(f"  [{'ผ่าน' if ok else 'ไม่ผ่าน'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def fake_vector(seed: float):
    import numpy as np

    v = np.full(face.EMBEDDING_DIM, seed, dtype="float32")
    return v / np.linalg.norm(v)


def main() -> int:
    conn = db_module.connect(Path(":memory:"))
    db_module.init_db(conn)
    now = thai.now().isoformat(timespec="seconds")

    print("1. นำเข้ารายชื่อนักศึกษา")
    with conn:
        r1 = repo.upsert_student(conn, student_id="6600000001", name="ทดสอบ หนึ่ง",
                                 year=2, program="วิทยาการคอมพิวเตอร์", advisor=None, now=now)
        r2 = repo.upsert_student(conn, student_id="6600000002", name="ทดสอบ สอง",
                                 year=3, program=None, advisor=None, now=now)
    check(r1 == "added" and r2 == "added", "เพิ่มนักศึกษาใหม่ได้ 2 คน")

    with conn:
        again = repo.upsert_student(conn, student_id="6600000001", name="ทดสอบ หนึ่ง (แก้ชื่อ)",
                                    year=3, program=None, advisor=None, now=now)
    check(again == "updated", "นำเข้าซ้ำถือเป็นการอัปเดต ไม่สร้างซ้ำ")
    check(
        repo.find_student_by_code(conn, "6600000001")["name"] == "ทดสอบ หนึ่ง (แก้ชื่อ)",
        "ชื่อถูกอัปเดตตามไฟล์ล่าสุด",
    )

    print("\n2. ลงทะเบียนใบหน้า")
    pk = repo.find_student_by_code(conn, "6600000001")["id"]
    with conn:
        cur = conn.execute(
            """INSERT INTO consents (student_id, purpose, policy_version, granted_at, method)
               VALUES (?, 'face_recognition', '2569-1', ?, 'kiosk_touch')""",
            (pk, now),
        )
        consent_id = cur.lastrowid
        conn.execute(
            """INSERT INTO face_embeddings
                   (student_id, consent_id, vector, dim, model, quality, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pk, consent_id, face.to_blob(fake_vector(0.5)),
             face.EMBEDDING_DIM, face.MODEL_TAG, 0.9, now),
        )

    registry = repo.registration_registry(conn)
    check(len(registry) == 1, "ทะเบียนแสดงผู้ลงทะเบียน 1 คน", f"{len(registry)} คน")
    check(registry[0]["studentId"] == "6600000001", "ทะเบียนชี้ไปที่คนที่ถูกต้อง")
    check(registry[0]["policyVersion"] == "2569-1", "ทะเบียนบอกฉบับความยินยอมที่ใช้")

    print("\n3. สิทธิขอดูข้อมูลของตนเอง")
    record = repo.student_record(conn, "6600000001")
    check(record is not None, "ดึงข้อมูลทั้งหมดของคนหนึ่งคนได้")
    check(len(record["faceEmbeddings"]) == 1, "แสดงจำนวนข้อมูลใบหน้าที่เก็บไว้")
    import json

    dumped = json.dumps(record, ensure_ascii=False)
    check("vector" not in dumped and "0.5" not in dumped,
          "ข้อมูลที่ส่งออกไม่มีค่าเวกเตอร์ดิบ (เป็นข้อมูลชีวภาพ)")
    check(repo.student_record(conn, "ไม่มีรหัสนี้") is None,
          "รหัสที่ไม่มีในระบบคืนค่าว่าง ไม่ใช่ข้อมูลของคนอื่น")

    print("\n4. ความยินยอมที่ค้างโดยไม่มีข้อมูลผูกไว้")
    pk2 = repo.find_student_by_code(conn, "6600000002")["id"]
    with conn:
        conn.execute(
            """INSERT INTO consents (student_id, purpose, policy_version, granted_at, method)
               VALUES (?, 'face_recognition', '2569-1', ?, 'kiosk_touch')""",
            (pk2, now),
        )
    orphans = repo.orphan_consents(conn)
    check(len(orphans) == 1 and orphans[0]["studentId"] == "6600000002",
          "ตรวจพบความยินยอมที่ยินยอมแล้วแต่ไม่ได้ถ่ายใบหน้าจนจบ")
    cleared = repo.clear_orphan_consents(conn, now)
    check(cleared == 1 and not repo.orphan_consents(conn), "ถอนความยินยอมที่ค้างได้")
    check(len(repo.registration_registry(conn)) == 1,
          "การล้างความยินยอมค้างไม่กระทบคนที่ลงทะเบียนจริง")

    print("\n5. สิทธิขอลบข้อมูลของตนเอง (ดำเนินการโดยสำนักงานสาขา)")
    result = repo.forget_student(conn, "6600000001", now)
    check(result["vectorsDeleted"] == 1, "ลบเวกเตอร์ใบหน้าทิ้งจริง")
    check(result["consentsRevoked"] == 1, "บันทึกการถอนความยินยอมไว้เป็นหลักฐาน")
    check(not repo.registration_registry(conn), "หายออกจากทะเบียนผู้ลงทะเบียนแล้ว")
    check(not face.load_enrolled(conn), "ระบบจำใบหน้านี้ไม่ได้อีกต่อไป")

    after = repo.student_record(conn, "6600000001")
    check(after is not None and not after["faceEmbeddings"],
          "ตัวนักศึกษาและตารางเรียนยังอยู่ ลบเฉพาะข้อมูลใบหน้า")
    check(all(c["revokedAt"] for c in after["consents"]),
          "ความยินยอมทุกรายการถูกทำเครื่องหมายว่าถอนแล้ว")
    check(repo.forget_student(conn, "ไม่มีรหัสนี้", now) is None,
          "สั่งลบรหัสที่ไม่มีในระบบไม่ทำอะไรเลย")

    conn.close()

    failed = [name for ok, name in _results if not ok]
    print(f"\n{'=' * 52}")
    print(f"ผ่าน {len(_results) - len(failed)}/{len(_results)} ข้อ")
    for name in failed:
        print(f"  ไม่ผ่าน: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
