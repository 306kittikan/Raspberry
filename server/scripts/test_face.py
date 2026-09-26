"""ทดสอบการรู้จำใบหน้าด้วยกล้องจริง

    .venv/Scripts/python.exe scripts/test_face.py --enroll 6604101001
    .venv/Scripts/python.exe scripts/test_face.py --recognize
    .venv/Scripts/python.exe scripts/test_face.py --check     (ตรวจระบบอย่างเดียว ไม่ใช้กล้อง)

เขียนไว้ให้ทดสอบส่วนกล้องได้โดยไม่ต้องเปิดหน้าเว็บ
--enroll จะเขียนข้อมูลจริงลงฐานข้อมูล พร้อมบันทึกความยินยอมให้ด้วย
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module, thai  # noqa: E402
from app.services import face  # noqa: E402
from app.services.camera import camera  # noqa: E402

SAMPLES = 8


def _boot() -> bool:
    print("กำลังเปิดกล้อง…")
    if not camera.start():
        print(f"  เปิดกล้องไม่ได้: {camera.error}")
        return False
    print(f"  กล้องพร้อม (source={camera.status()['source']})")

    print("กำลังโหลดโมเดลรู้จำใบหน้า…")
    if not face.engine.load():
        print(f"  โหลดโมเดลไม่ได้: {face.engine.error}")
        return False
    print(f"  โมเดลพร้อม ({face.MODEL_TAG})")
    return True


def cmd_check() -> int:
    conn = db_module.connect()
    enrolled = face.load_enrolled(conn)
    by_student: dict[int, int] = {}
    for pk, _ in enrolled:
        by_student[pk] = by_student.get(pk, 0) + 1

    print(f"เวกเตอร์ใบหน้าที่ใช้งานได้ {len(enrolled)} รายการ จาก {len(by_student)} คน")
    for pk, count in by_student.items():
        row = conn.execute("SELECT name, student_id FROM students WHERE id = ?", (pk,)).fetchone()
        name = row["name"] if row else f"(ไม่พบ id={pk})"
        print(f"  {name} — {count} เวกเตอร์")

    orphan = conn.execute(
        """SELECT COUNT(*) c FROM face_embeddings f
           LEFT JOIN consents c2 ON c2.id = f.consent_id AND c2.revoked_at IS NULL
           WHERE c2.id IS NULL"""
    ).fetchone()["c"]
    print(f"เวกเตอร์ที่ความยินยอมถูกถอนแล้ว (ต้องเป็น 0): {orphan}")
    conn.close()
    return 0 if orphan == 0 else 1


def _grab_samples(label: str) -> list:
    samples = []
    last_seq = -1
    started = time.time()
    print(f"\n{label}")
    print("  มองตรงมาที่กล้อง แล้วขยับหน้าซ้าย–ขวาเล็กน้อย")

    while len(samples) < SAMPLES and time.time() - started < 30:
        frame, seq = camera.wait_for_frame(last_seq, timeout=2.0)
        if frame is None:
            continue
        last_seq = seq
        faces = [f for f in face.engine.detect(frame) if not f.too_small]

        if len(faces) > 1:
            print("\r  พบหลายใบหน้า — ขอทีละคน                    ", end="")
            continue
        if not faces:
            print("\r  ยังไม่พบใบหน้า…                            ", end="")
            continue

        samples.append(faces[0].embedding)
        bar = "█" * len(samples) + "░" * (SAMPLES - len(samples))
        print(f"\r  เก็บตัวอย่าง {bar} {len(samples)}/{SAMPLES}   ", end="")
        time.sleep(0.35)

    print()
    return samples


def cmd_enroll(student_code: str) -> int:
    if not _boot():
        return 2

    conn = db_module.connect()
    student = conn.execute(
        "SELECT id, name FROM students WHERE student_id = ?", (student_code,)
    ).fetchone()
    if student is None:
        print(f"ไม่พบรหัสนักศึกษา {student_code}")
        return 1

    samples = _grab_samples(f"ลงทะเบียนใบหน้าให้ {student['name']}")
    if len(samples) < SAMPLES:
        print("เก็บตัวอย่างไม่ครบ ยกเลิก")
        return 1

    quality = face.sample_quality(samples)
    vector = face.average_embedding(samples)
    print(f"  ความสอดคล้องของตัวอย่าง {quality:.3f}")

    others = [(pk, v) for pk, v in face.load_enrolled(conn) if pk != student["id"]]
    clash = face.match(vector, others)
    if clash.student_pk is not None:
        print(f"  ใบหน้านี้ตรงกับผู้ใช้อื่นอยู่แล้ว (score={clash.score:.3f}) ยกเลิก")
        return 1

    now = thai.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            """INSERT INTO consents (student_id, purpose, policy_version, granted_at, method)
               VALUES (?, 'face_recognition', 'test-script', ?, 'cli')""",
            (student["id"], now),
        )
        conn.execute(
            """INSERT INTO face_embeddings
                   (student_id, consent_id, vector, dim, model, quality, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student["id"], cur.lastrowid, face.to_blob(vector),
             face.EMBEDDING_DIM, face.MODEL_TAG, quality, now),
        )
    print(f"  บันทึกเรียบร้อย (consent_id={cur.lastrowid})")
    conn.close()
    return 0


def cmd_recognize() -> int:
    if not _boot():
        return 2

    conn = db_module.connect()
    enrolled = face.load_enrolled(conn)
    if not enrolled:
        print("ยังไม่มีใครลงทะเบียนใบหน้า — รัน --enroll ก่อน")
        return 1

    print(f"\nเทียบกับ {len(enrolled)} เวกเตอร์ · เกณฑ์ {face.config.FACE_MATCH_THRESHOLD}")
    print("ยืนหน้ากล้อง (กด Ctrl+C เพื่อหยุด)\n")

    last_seq = -1
    try:
        while True:
            frame, seq = camera.wait_for_frame(last_seq, timeout=2.0)
            if frame is None:
                continue
            last_seq = seq

            t0 = time.perf_counter()
            faces = [f for f in face.engine.detect(frame) if not f.too_small]
            detect_ms = (time.perf_counter() - t0) * 1000

            if not faces:
                print("\r  ยังไม่พบใบหน้า…                                          ", end="")
                time.sleep(0.2)
                continue
            if len(faces) > 1:
                print(f"\r  พบ {len(faces)} ใบหน้า — ขอทีละคน                        ", end="")
                time.sleep(0.2)
                continue

            result = face.match(faces[0].embedding, enrolled)
            if result.student_pk is None:
                print(f"\r  จำไม่ได้ ({result.reason}) score={result.score:.3f} "
                      f"· ตรวจจับ {detect_ms:.0f} ms      ", end="")
            else:
                row = conn.execute(
                    "SELECT name FROM students WHERE id = ?", (result.student_pk,)
                ).fetchone()
                margin = result.score - result.runner_up
                print(f"\r  → {row['name']}  score={result.score:.3f} "
                      f"margin={margin:.3f} · ตรวจจับ {detect_ms:.0f} ms   ", end="")
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nหยุดแล้ว")
    finally:
        conn.close()
        camera.stop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ทดสอบการรู้จำใบหน้าด้วยกล้องจริง")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enroll", metavar="รหัสนักศึกษา")
    group.add_argument("--recognize", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        if args.check:
            return cmd_check()
        if args.enroll:
            return cmd_enroll(args.enroll)
        return cmd_recognize()
    finally:
        camera.stop()


if __name__ == "__main__":
    sys.exit(main())
