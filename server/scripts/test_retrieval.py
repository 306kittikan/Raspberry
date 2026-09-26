"""ตรวจว่าการค้นเอกสารภาษาไทยหาชิ้นเอกสารที่ถูกต้องเจอหรือไม่

    .venv/Scripts/python.exe scripts/test_retrieval.py

ทดสอบเฉพาะขั้นตอนค้นเอกสาร ไม่ต้องใช้กุญแจ API และไม่เรียกโมเดล
ถ้าขั้นนี้ค้นไม่เจอ ผู้ช่วย AI จะตอบ "ไม่พบข้อมูล" ทุกครั้งไม่ว่าโมเดลจะเก่งแค่ไหน
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module  # noqa: E402
from app.services import retrieval  # noqa: E402

# (คำถาม, ข้อความที่ต้องปรากฏในชิ้นเอกสารอันดับต้น ๆ)
CASES = [
    ("สาขามีห้องปฏิบัติการอะไรบ้าง", "ปฏิบัติการคอมพิวเตอร์"),
    ("ผศ.ภานุวัฒน์ เมฆะ สอนอะไร", "ภานุวัฒน์"),
    ("วิชาการพัฒนาเว็บแอปพลิเคชันเรียนอะไร", "เว็บแอปพลิเคชัน"),
    ("หลักสูตรมีกี่หน่วยกิต", "หน่วยกิต"),
    ("ติดต่อสาขาได้ทางไหน", "cs@mju.ac.th"),
    ("ประวัติความเป็นมาของสาขา", "2536"),
    ("ปัญญาประดิษฐ์เรียนวิชาอะไรบ้าง", "ปัญญาประดิษฐ์"),
]

TOP_K = 5


def main() -> int:
    conn = db_module.connect()
    total = conn.execute("SELECT COUNT(*) c FROM doc_chunks").fetchone()["c"]
    print(f"ชิ้นเอกสารในระบบ {total} ชิ้น · ค้นครั้งละ {TOP_K} อันดับแรก\n")

    failed = []
    for question, expected in CASES:
        hits = retrieval.search(conn, question, limit=TOP_K)
        found_at = next(
            (i + 1 for i, h in enumerate(hits) if expected in h["content"] or expected in h["title"]),
            None,
        )
        ok = found_at is not None
        if not ok:
            failed.append(question)

        top = hits[0]["title"][:46] if hits else "(ไม่พบอะไรเลย)"
        rank = f"อันดับ {found_at}" if ok else "ไม่พบ"
        print(f"  [{'ผ่าน' if ok else 'ไม่ผ่าน'}] {question}")
        print(f"          ค้นได้ {len(hits)} ชิ้น · อันดับ 1: {top} · คำที่ต้องเจอ: {rank}")

    # คำถามที่ไม่เกี่ยวกับสาขาเลย ควรค้นไม่เจอหรือเจอน้อย
    junk = retrieval.search(conn, "ราคาทองคำวันนี้เท่าไร", limit=TOP_K)
    print(f"\n  คำถามนอกเรื่อง 'ราคาทองคำวันนี้เท่าไร' → ค้นได้ {len(junk)} ชิ้น")
    print("          (ผู้ช่วย AI จะตอบ 'ไม่พบข้อมูล' เพราะเอกสารเหล่านี้ไม่มีคำตอบ)")

    conn.close()
    print(f"\n{'=' * 52}")
    print(f"ผ่าน {len(CASES) - len(failed)}/{len(CASES)} ข้อ")
    for q in failed:
        print(f"  ไม่ผ่าน: {q}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
