"""จับคู่ประโยคที่ผู้ใช้พูด กับคำถามที่ระบบตอบได้

ภาษาไทยไม่เว้นวรรคระหว่างคำ และการถอดความจากเสียงมักสะกดเพี้ยนเล็กน้อย
จึงเทียบด้วยสองชั้น

ชั้นที่ 1 คำสำคัญ — ใช้กับคำถามที่ต้องตอบจากฐานข้อมูลเท่านั้น
  (ตารางเรียน ห้องเรียน กำหนดสอบ) เพราะกลุ่มนี้ห้ามตอบผิด
  ถ้าเจอคำสำคัญชัดเจนให้ตัดสินทันที ไม่ต้องเดาด้วยความคล้าย

ชั้นที่ 2 ความคล้ายของตัวอักษร — ใช้กับคำถามที่เหลือ
  วัดด้วยสัดส่วนสตริงย่อยสามตัวอักษรที่ตรงกัน (Dice coefficient)

ถ้าไม่เข้าข่ายทั้งสองชั้น จะถือเป็นคำถามปลายเปิด แล้วส่งให้ผู้ช่วย AI
ค้นเอกสารของสาขาตอบ ซึ่งยังต้องอ้างอิงเอกสารเสมอตามกติกาเดิม
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

_NOISE = re.compile(r"[^\wก-๙]+", re.UNICODE)

# คำที่บ่งบอกว่าผู้ถามหมายถึง "หลักสูตร" ไม่ใช่ "ตารางเรียนของฉัน"
# ต้องกันไว้ เพราะ "หลักสูตรเรียนอะไรบ้าง" มีคำว่า "เรียนอะไร" อยู่ด้วย
# แล้วจะกลายเป็นการดึงตารางเรียนส่วนบุคคลมาตอบผิดคำถาม
CURRICULUM_WORDS = ["หลักสูตร", "รายวิชาทั้งหมด", "แผนการศึกษา", "หน่วยกิต", "วิชาเอก", "วิชาเลือก"]

# คำสำคัญของคำถามที่ต้องตอบจากฐานข้อมูล เรียงจากเฉพาะเจาะจงมากไปน้อย
# กฎแรกที่เข้าเงื่อนไขเป็นผู้ชนะ จึงต้องวางวลีที่ชัดเจนที่สุดไว้บนสุด
# รูปแบบ: (id คำถาม, คำที่ต้องพบอย่างน้อยหนึ่งคำ, คำที่ห้ามพบ)
KEYWORD_RULES: list[tuple[str, list[str], list[str]]] = [
    # วลีที่ระบุชัดว่าถามถึงคาบถัดไป ชนะกฎเรื่องห้องเสมอ
    # เพราะ "คาบต่อไปเรียนที่ห้องไหน" ต้องการชื่อวิชาและเวลาด้วย ไม่ใช่แค่เลขชั้น
    ("next-class", ["คาบต่อไป", "คาบถัดไป", "คาบหน้า", "วิชาต่อไป", "วิชาถัดไป"],
     ["สอบ", *CURRICULUM_WORDS]),

    ("exam-subject", ["สอบ", "กําหนดสอบ", "กำหนดสอบ", "ตารางสอบ"], []),

    ("room-floor", ["ชั้นไหน", "ชั้นอะไร", "ห้องอยู่", "อยู่ชั้น", "ไปห้อง", "ห้องไหน"],
     ["สอบ"]),

    ("next-class", ["เรียนอะไร", "เรียนที่ไหน", "ตารางเรียน", "เรียนกี่โมง", "เรียนห้องไหน"],
     ["สอบ", *CURRICULUM_WORDS]),

    # ดักเฉพาะการถามแบบกว้าง ๆ ว่าจะติดต่ออาจารย์ได้อย่างไร
    # เดิมดักด้วยคำว่า "อาจารย์" เฉย ๆ ทำให้คำถามที่เจาะจงกว่านั้นถูกกลืนไปด้วย
    # "อีเมลอาจารย์พาสน์คืออะไร" จึงเคยได้ผู้สอนของคาบถัดไปเป็นคำตอบ ซึ่งคนละคนกัน
    ("contact-teacher",
     ["ติดต่ออาจารย์", "อาจารย์ที่ปรึกษา", "ที่ปรึกษาคือ", "ที่ปรึกษาของฉัน",
      "ผู้สอนวิชานี้", "ติดต่อผู้สอน", "อาจารย์ผู้สอน"],
     []),
    ("office-contact", ["สำนักงาน", "สํานักงาน", "ธุรการ", "ติดต่อสาขา"], []),
]

# ความคล้ายขั้นต่ำที่ยอมรับว่าเป็นคำถามเดียวกัน
SIMILARITY_THRESHOLD = 0.34


@dataclass(slots=True)
class Intent:
    question_id: str | None
    confidence: float
    method: str  # 'keyword' | 'similarity' | 'open'


def _normalise(text: str) -> str:
    return _NOISE.sub("", text)


def _trigrams(text: str) -> set[str]:
    flat = _normalise(text)
    if len(flat) < 3:
        return {flat} if flat else set()
    return {flat[i : i + 3] for i in range(len(flat) - 2)}


def similarity(a: str, b: str) -> float:
    """Dice coefficient ของสตริงย่อยสามตัวอักษร คืนค่า 0–1"""
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2 * len(ta & tb) / (len(ta) + len(tb))


def match(conn: sqlite3.Connection, text: str) -> Intent:
    flat = _normalise(text)
    if not flat:
        return Intent(None, 0.0, "open")

    # คำถามที่เอ่ยชื่อบุคลากรตรง ๆ มีคำตอบแน่นอนอยู่ในฐานข้อมูล
    # ตอบจากตารางได้เลย แม่นกว่าและทำงานได้แม้ตู้ออฟไลน์
    # ต้องตรวจก่อนกฎคำสำคัญ ไม่งั้นจะถูกกฎ contact-teacher กลืนไปก่อน
    from .. import repo

    if repo.find_personnel_mention(conn, text) is not None:
        return Intent("person-detail", 1.0, "person")

    # "ใครสอนเรื่อง X" ตอบได้ครบทุกคนจากคอลัมน์ความเชี่ยวชาญ
    # ต้องมีคำที่บ่งว่าถามหา "คน" ด้วย ไม่งั้น "เรียน IoT ที่ไหน"
    # ซึ่งถามถึงหลักสูตร จะถูกตอบเป็นรายชื่ออาจารย์แทน
    if any(w in flat for w in ("ใคร", "อาจารย์คนไหน", "คนไหนสอน", "ท่านไหน",
                               "อาจารย์ท่านใด", "ผู้เชี่ยวชาญ", "เชี่ยวชาญด้าน",
                               "ถนัดเรื่อง", "สอนเรื่อง", "ปรึกษาเรื่อง")):
        if repo.search_personnel_by_topic(conn, text):
            return Intent("person-topic", 1.0, "person")

    active = {
        row["id"]: row["label"]
        for row in conn.execute(
            "SELECT id, label FROM quick_questions WHERE active = 1"
        ).fetchall()
    }

    # ---- ชั้นที่ 1: คำสำคัญ ----
    for qid, keywords, avoid in KEYWORD_RULES:
        if qid not in active:
            continue
        if any(_normalise(bad) in flat for bad in avoid):
            continue
        if any(_normalise(word) in flat for word in keywords):
            return Intent(qid, 1.0, "keyword")

    # ---- ชั้นที่ 2: ความคล้ายกับข้อความบนปุ่ม ----
    best_id, best_score = None, 0.0
    for qid, label in active.items():
        score = similarity(text, label)
        if score > best_score:
            best_id, best_score = qid, score

    if best_score >= SIMILARITY_THRESHOLD:
        return Intent(best_id, round(best_score, 3), "similarity")

    return Intent(None, round(best_score, 3), "open")
