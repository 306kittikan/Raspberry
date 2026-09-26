"""ค้นเอกสารของสาขาเพื่อส่งเป็นบริบทให้ผู้ช่วย AI

ภาษาไทยไม่เว้นวรรคระหว่างคำ ตัวตัดคำมาตรฐานของ FTS5 จึงใช้ไม่ได้
ที่นี่ใช้ tokenizer แบบ trigram ซึ่งจับคู่ด้วย "สตริงย่อย" แทนการตัดคำ
จึงค้นภาษาไทยได้โดยไม่ต้องพึ่งพจนานุกรมหรือไลบรารีตัดคำเพิ่ม
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

# ตัดอักขระที่ไม่ใช่ตัวอักษร/ตัวเลขออกก่อนสร้างหน้าต่างค้นหา
_NOISE = re.compile(r"[^\wก-๙]+", re.UNICODE)

WINDOW = 6  # ความยาวสตริงย่อยที่ใช้ค้น
STEP = 3    # ระยะเลื่อนหน้าต่าง (ซ้อนกันเพื่อไม่ให้พลาดรอยต่อคำ)


def _windows(text: str) -> list[str]:
    """แตกคำถามเป็นสตริงย่อยซ้อนกัน เช่น 'เพิ่มถอนรายวิชา' → 'เพิ่มถอนร', 'ถอนรายวิ', ..."""
    flat = _NOISE.sub("", text)
    if len(flat) < 3:
        return []
    if len(flat) <= WINDOW:
        return [flat]
    return [flat[i : i + WINDOW] for i in range(0, len(flat) - WINDOW + 1, STEP)]


def _fts_query(text: str) -> str | None:
    """ประกอบเป็นนิพจน์ FTS5 โดยครอบเครื่องหมายคำพูดกันอักขระพิเศษ"""
    parts = [f'"{w}"' for w in _windows(text)]
    return " OR ".join(parts) if parts else None


def search(conn: sqlite3.Connection, question: str, limit: int = 5) -> list[dict[str, Any]]:
    """คืนชิ้นเอกสารที่เกี่ยวข้องที่สุด พร้อมข้อมูลอ้างอิงของเอกสารต้นทาง"""
    query = _fts_query(question)
    if query is None:
        return []

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
        (query, limit),
    ).fetchall()

    return [
        {
            "chunkId": r["id"],
            "content": r["content"],
            "page": r["page"],
            "documentId": r["document_id"],
            "title": r["title"],
            "citationLabel": r["citation_label"],
            "effectiveDate": r["effective_date"],
        }
        for r in rows
    ]


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
