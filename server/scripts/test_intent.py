"""ตรวจว่าประโยคที่ผู้ใช้พูดถูกจับคู่กับคำถามที่ถูกต้อง

    .venv/Scripts/python.exe scripts/test_intent.py

ไม่ต้องใช้ไมโครโฟนหรือกุญแจ API ทดสอบเฉพาะขั้นตีความคำถาม
ข้อที่สำคัญที่สุดคือคำถามเกี่ยวกับหลักสูตรต้องไม่ถูกตีความเป็นตารางเรียนส่วนบุคคล
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module  # noqa: E402
from app.services import intent  # noqa: E402

# (ประโยคที่พูด, id คำถามที่ควรได้, คำอธิบายว่าทำไมต้องเป็นแบบนั้น)
CASES: list[tuple[str, str | None, str]] = [
    # คำถามที่เอ่ยชื่ออาจารย์ ต้องแยกให้ออกว่าถามเรื่องอะไรเกี่ยวกับท่าน
    # เคยพังมาแล้ว ทุกคำถามที่มีชื่ออาจารย์ถูกตอบเป็นนามบัตรหมด
    ("ตารางสอนอาจารย์ภานุวัฒน์", "instructor-schedule",
     "ถามตารางสอน ต้องได้คาบสอนทั้งสัปดาห์ ไม่ใช่เบอร์โทรกับอีเมล"),
    ("อาจารย์กิตติกร สอนอะไรบ้าง", "instructor-schedule", ""),
    ("อ.ปวีณ สอนวันไหนบ้าง", "instructor-schedule", ""),
    ("อาจารย์ภานุวัฒน์ ตอนนี้สอนอยู่ไหม", "instructor-now",
     "ถามว่าเดินไปตอนนี้จะเจอไหม คนละคำถามกับตารางสอนทั้งสัปดาห์"),
    ("อีเมลอาจารย์ภานุวัฒน์", "person-detail",
     "ถามช่องทางติดต่อ ต้องได้นามบัตร ไม่ใช่ตารางสอน"),
    ("คาบต่อไปเรียนที่ห้องไหน", "next-class",
     "ถามคาบถัดไป ต้องได้ชื่อวิชาและเวลาด้วย ไม่ใช่แค่เลขชั้น"),
    ("คาบถัดไปเรียนกี่โมง", "next-class", ""),
    ("วิชาต่อไปคือวิชาอะไร", "next-class", ""),
    ("ห้องเรียนนี้อยู่ชั้นไหน", "room-floor", ""),
    ("ห้องนี้อยู่ตึกไหนชั้นอะไร", "room-floor", ""),
    ("ขอกำหนดสอบวิชานี้หน่อย", "exam-subject", ""),
    ("สอบกลางภาคห้องไหน", "exam-subject",
     "มีคำว่าห้องไหนแต่ถามเรื่องสอบ ต้องไม่ตกไปที่ room-floor"),
    ("ตารางสอบปลายภาคเมื่อไหร่", "exam-subject", ""),
    ("ติดต่ออาจารย์ที่ปรึกษาได้ที่ไหน", "contact-teacher", ""),
    ("อาจารย์ผู้สอนชื่ออะไร", "contact-teacher", ""),
    ("สำนักงานสาขาอยู่ตรงไหน", "office-contact", ""),
    ("เพิ่มถอนรายวิชาต้องทำยังไง", "add-drop", ""),
    ("สหกิจศึกษาต้องเตรียมอะไรบ้าง", "coop", ""),
    ("หลักสูตรเรียนอะไรบ้าง", "curriculum",
     "มีคำว่าเรียนอะไร แต่ถามถึงหลักสูตร ห้ามดึงตารางเรียนส่วนบุคคลมาตอบ"),
    ("สาขามีห้องปฏิบัติการอะไรบ้าง", "facilities", ""),
    ("หลักสูตรมีกี่หน่วยกิต", None, "คำถามปลายเปิด ให้ผู้ช่วย AI ค้นเอกสารตอบ"),
    ("ประวัติของสาขาเป็นมายังไง", None, ""),
    ("วันนี้อากาศเป็นยังไง", None, "ไม่เกี่ยวกับสาขา ต้องไม่เดาว่าเป็นคำถามใด"),
    ("", None, "เสียงว่าง"),
]


def main() -> int:
    conn = db_module.connect()
    failed: list[str] = []

    for text, expected, why in CASES:
        got = intent.match(conn, text)
        ok = got.question_id == expected
        if not ok:
            failed.append(text)
        label = text or "(ว่าง)"
        print(f"  [{'ผ่าน' if ok else 'ไม่ผ่าน'}] {label:34s} → "
              f"{str(got.question_id):16s} [{got.method}]")
        if why:
            print(f"          {why}")
        if not ok:
            print(f"          คาดหวัง {expected}")

    conn.close()
    print(f"\n{'=' * 52}")
    print(f"ผ่าน {len(CASES) - len(failed)}/{len(CASES)} ข้อ")
    for text in failed:
        print(f"  ไม่ผ่าน: {text}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
