"""ค้นเอกสารของสาขาเพื่อส่งเป็นบริบทให้ผู้ช่วย AI

ภาษาไทยไม่เว้นวรรคระหว่างคำ ตัวตัดคำมาตรฐานของ FTS5 จึงใช้ไม่ได้
ที่นี่ใช้ tokenizer แบบ trigram ซึ่งจับคู่ด้วย "สตริงย่อย" แทนการตัดคำ
จึงค้นภาษาไทยได้โดยไม่ต้องพึ่งพจนานุกรมหรือไลบรารีตัดคำเพิ่ม

การค้นทำสองชั้น เพราะชั้นเดียวเลือกได้อย่างเดียวระหว่างหาเจอกับหาไม่มั่ว

ชั้นที่ 1 — หว่านให้กว้าง
  แตกคำถามเป็นสตริงย่อยสั้น ๆ ซ้อนกันแล้วค้นแบบ OR
  สตริงย่อยยาว ๆ พลาดง่าย เพราะฝั่งคำถามถูกตัดช่องว่างออกหมด
  แต่ในเอกสารยังมีช่องว่างและวงเล็บคั่นอยู่ เช่น คำถาม "อีเมลสาขาคืออะไร"
  ให้สตริง "อีเมลส" ซึ่งไม่มีวันตรงกับเอกสารที่เขียนว่า "อีเมล (ติดต่อสอบถาม)"

ชั้นที่ 2 — กรองด้วยสัดส่วนที่ตรงจริง
  สตริงย่อยสั้นทำให้เอกสารที่ไม่เกี่ยวเลยก็ติดมาด้วย เช่น "ราคาทองคำวันนี้"
  ไปตรงกับ "วันนี้" ในเอกสารตารางกิจกรรม จึงนับว่าคำถามหนึ่งคำถาม
  มีสตริงย่อยไปตรงกับชิ้นนั้นกี่ส่วนจากทั้งหมด ถ้าน้อยเกินเกณฑ์ถือว่าไม่เกี่ยว

  ขั้นนี้สำคัญกว่าที่คิด เพราะการส่งเอกสารที่ไม่เกี่ยวไปให้โมเดลอ่าน
  ทั้งเสียเงินเปล่าและเพิ่มโอกาสที่โมเดลจะตีความเกินจริงจากข้อความที่ไม่เกี่ยวข้อง

วัดผลได้ด้วย  .venv/Scripts/python.exe scripts/eval_retrieval.py
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

# ตัดอักขระที่ไม่ใช่ตัวอักษร/ตัวเลขออกก่อนสร้างหน้าต่างค้นหา
_NOISE = re.compile(r"[^\wก-๙]+", re.UNICODE)

# ค่าทั้งสามนี้เลือกจากการวัดผลจริง ไม่ได้ตั้งตามความรู้สึก
# ดูตารางเปรียบเทียบได้ใน README หัวข้อ "คุณภาพการค้นเอกสาร"
WINDOW = 3  # ความยาวสตริงย่อยที่ใช้ค้น
STEP = 1    # ระยะเลื่อนหน้าต่าง (ซ้อนกันเพื่อไม่ให้พลาดรอยต่อคำ)

# ต้องมีสตริงย่อยของคำถามไปตรงกับชิ้นเอกสารอย่างน้อยสัดส่วนนี้
# ต่ำกว่านี้เอกสารที่ไม่เกี่ยวจะหลุดเข้ามา สูงกว่านี้คำถามที่ตอบได้จะเริ่มหาไม่เจอ
MIN_COVERAGE = 0.28

# ดึงมาจาก FTS มากกว่าที่ต้องใช้กี่เท่า เผื่อให้ชั้นกรองมีของให้เลือก
POOL_FACTOR = 6


def _windows(text: str) -> list[str]:
    """แตกคำถามเป็นสตริงย่อยซ้อนกัน เช่น 'เพิ่มถอนรายวิชา' → 'เพิ่ม', 'พิ่มถ', ..."""
    flat = _NOISE.sub("", text).lower()
    if len(flat) < 3:
        return []
    if len(flat) <= WINDOW:
        return [flat]
    return [flat[i : i + WINDOW] for i in range(0, len(flat) - WINDOW + 1, STEP)]


# คำที่นักศึกษาพูด แต่ในเอกสารเขียนอีกอย่าง
#
# การค้นแบบสตริงย่อยเทียบตัวอักษรตรง ๆ จึงข้ามช่องว่างนี้เองไม่ได้
# ต่างจากการค้นด้วยเวกเตอร์ความหมาย ซึ่งต้องใช้โมเดลฝังตัวและแรงเครื่องที่ตู้ไม่มี
# ตารางเล็ก ๆ ตารางนี้แลกความครอบคลุมกับความเรียบง่ายและความเร็ว
# เพิ่มรายการใหม่เมื่อ eval_retrieval.py ชี้ว่าคำถามแบบไหนหาไม่เจอ
SYNONYMS = {
    "เฟซบุ๊ก": "facebook", "เฟสบุ๊ค": "facebook", "เฟสบุ๊ก": "facebook",
    "เฟซบุ๊ค": "facebook", "เฟซบุ้ค": "facebook",
    "ไลน์": "line",
    "เอไอ": "ปัญญาประดิษฐ์", "ไอโอที": "iot",
    "ปีหนึ่ง": "ชั้นปีที่1", "ปี1": "ชั้นปีที่1",
    "ปีสอง": "ชั้นปีที่2", "ปี2": "ชั้นปีที่2",
    "ปีสาม": "ชั้นปีที่3", "ปี3": "ชั้นปีที่3",
    "ปีสี่": "ชั้นปีที่4", "ปี4": "ชั้นปีที่4",
}


def _variants(text: str) -> list[str]:
    """คำถามฉบับเดิม และฉบับที่แทนคำพูดด้วยคำที่ใช้จริงในเอกสาร

    คืนสองฉบับแยกกัน ไม่ใช่รวมเป็นสตริงเดียว เพราะการคิดสัดส่วนที่ตรง
    ต้องคิดแยกฉบับ ถ้ารวมกันฉบับที่ไม่เกี่ยวจะไปเจือจางสัดส่วนของอีกฉบับ
    """
    flat = _NOISE.sub("", text).lower()
    swapped = flat
    for spoken, written in SYNONYMS.items():
        swapped = swapped.replace(spoken, written)
    return [flat] if swapped == flat else [flat, swapped]


def _fts_query(text: str) -> str | None:
    """ประกอบเป็นนิพจน์ FTS5 โดยครอบเครื่องหมายคำพูดกันอักขระพิเศษ"""
    seen = {w for variant in _variants(text) for w in _windows(variant)}
    parts = [f'"{w}"' for w in sorted(seen)]
    return " OR ".join(parts) if parts else None


def _coverage(windows: set[str], content: str) -> float:
    """สัดส่วนสตริงย่อยของคำถามที่ปรากฏในชิ้นเอกสารนี้จริง ๆ

    ใช้แทนคะแนน bm25 ในการเรียงลำดับ เพราะ bm25 ให้น้ำหนักกับคำที่พบน้อย
    ซึ่งกับสตริงย่อยภาษาไทยมักเป็นเศษคำที่บังเอิญตรง ไม่ใช่คำที่ผู้ถามหมายถึง
    """
    if not windows:
        return 0.0
    low = content.lower()
    return sum(1 for w in windows if w in low) / len(windows)


def search(conn: sqlite3.Connection, question: str, limit: int = 5) -> list[dict[str, Any]]:
    """คืนชิ้นเอกสารที่เกี่ยวข้องที่สุด พร้อมข้อมูลอ้างอิงของเอกสารต้นทาง"""
    query = _fts_query(question)
    if query is None:
        return []

    # คิดสัดส่วนแยกแต่ละฉบับแล้วเอาค่าที่ดีที่สุด
    variants = [set(_windows(v)) for v in _variants(question)]

    rows = conn.execute(
        """
        SELECT ch.id, ch.content, ch.page,
               d.id AS document_id, d.title, d.citation_label, d.effective_date
        FROM doc_chunks_fts f
        JOIN doc_chunks ch ON ch.id = f.rowid
        JOIN documents  d  ON d.id = ch.document_id
        WHERE doc_chunks_fts MATCH ?
        ORDER BY bm25(doc_chunks_fts)
        LIMIT ?
        """,
        (query, limit * POOL_FACTOR),
    ).fetchall()

    scored = []
    for order, r in enumerate(rows):
        coverage = max(_coverage(w, r["content"]) for w in variants)
        if coverage < MIN_COVERAGE:
            continue
        scored.append((
            -coverage,
            order,   # คะแนนเท่ากันให้ยึดลำดับเดิมจาก bm25
            {
                "chunkId": r["id"],
                "content": r["content"],
                "page": r["page"],
                "documentId": r["document_id"],
                "title": r["title"],
                "citationLabel": r["citation_label"],
                "effectiveDate": r["effective_date"],
                "coverage": round(coverage, 3),
            },
        ))

    scored.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in scored[:limit]]


def citation_for_chunk(conn: sqlite3.Connection, chunk_id: int) -> str | None:
    """ดึงข้อความอ้างอิงจากฐานข้อมูล — ไม่ใช่จากสิ่งที่โมเดลพิมพ์กลับมา"""
    row = conn.execute(
        """
        SELECT d.citation_label, ch.page
        FROM doc_chunks ch
        JOIN documents d ON d.id = ch.document_id
        WHERE ch.id = ?
        """,
        (chunk_id,),
    ).fetchone()
    if row is None:
        return None
    return f"{row['citation_label']} {row['page']}" if row["page"] else row["citation_label"]
