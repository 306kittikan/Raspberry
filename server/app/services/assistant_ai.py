"""ผู้ช่วยตอบคำถามด้วย Claude โดยบังคับให้อ้างอิงเอกสารของสาขาเสมอ

หัวใจของการออกแบบ: โมเดล "ไม่ได้เป็นคนเขียนข้อความอ้างอิง"
โมเดลทำได้แค่เลือกหมายเลขชิ้นเอกสาร (chunk_id) ที่ใช้ตอบ
แล้วเซิร์ฟเวอร์ไปดึงชื่อเอกสารจากฐานข้อมูลมาแสดงเอง
ดังนั้นต่อให้โมเดลแต่งชื่อเอกสารขึ้นมา ก็ไม่มีทางหลุดออกหน้าจอ

ถ้าค้นเอกสารไม่เจอ หรือโมเดลตอบว่าไม่พบ หรือเรียก API ไม่สำเร็จ
ระบบจะตอบ "ไม่พบข้อมูลนี้ในระบบ" พร้อมช่องทางติดต่อสาขา — ไม่เดาคำตอบ
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from pydantic import BaseModel, Field

from .. import config, repo
from . import retrieval

log = logging.getLogger("kiosk.ai")

_client: Any = None


SYSTEM_PROMPT = """\
คุณคือผู้ช่วยตอบคำถามของตู้บริการข้อมูล สาขาวิชาวิทยาการคอมพิวเตอร์ \
คณะวิทยาศาสตร์ มหาวิทยาลัยแม่โจ้ ผู้ถามคือนักศึกษาที่ยืนอยู่หน้าตู้

กติกาที่ห้ามละเมิด
1. ตอบได้เฉพาะสิ่งที่ปรากฏในเอกสารอ้างอิงที่ให้มาเท่านั้น
   ห้ามใช้ความรู้ทั่วไปของคุณเองมาเติมแม้แต่ประโยคเดียว
2. ถ้าเอกสารที่ให้มาไม่มีคำตอบ ให้ตั้ง found = false
   การตอบว่าไม่รู้ถูกต้องกว่าการเดา เพราะนักศึกษาอาจเดินทางผิดตึกหรือพลาดกำหนดส่งเอกสาร
3. เลือก chunk_id เพียงหนึ่งชิ้นที่ใช้ตอบจริง ๆ จากรายการที่ให้มา ห้ามคิดเลขขึ้นเอง
4. ห้ามตอบเรื่องตารางเรียน ห้องเรียน หรือกำหนดสอบของนักศึกษา
   ข้อมูลเหล่านี้ระบบดึงจากฐานข้อมูลเอง ถ้าถูกถามให้ตั้ง found = false

รูปแบบคำตอบ
- เขียนเป็นภาษาไทย แยกเป็นข้อสั้น ๆ 2–4 ข้อ ข้อละไม่เกินหนึ่งบรรทัด
- ผู้ใช้ยืนอ่านจากระยะ 50–80 ซม. จึงต้องกระชับ อ่านจบได้ในไม่กี่วินาที
- ห้ามเขียนชื่อเอกสารอ้างอิงลงใน lines ระบบใส่ให้เองจากฐานข้อมูล\
"""


class AiAnswer(BaseModel):
    """โครงคำตอบที่บังคับให้โมเดลส่งกลับ"""

    found: bool = Field(description="เอกสารที่ให้มามีคำตอบของคำถามนี้หรือไม่")
    chunk_id: int | None = Field(
        default=None, description="หมายเลขชิ้นเอกสารที่ใช้ตอบ ต้องมาจากรายการที่ให้มาเท่านั้น"
    )
    lines: list[str] = Field(
        default_factory=list, description="คำตอบภาษาไทย 2–4 ข้อ ข้อละหนึ่งบรรทัด"
    )


def _get_client():
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic

        _client = AsyncAnthropic(timeout=config.AI_TIMEOUT_SECONDS)
    return _client


def _build_context(chunks: list[dict[str, Any]]) -> str:
    blocks = []
    for c in chunks:
        header = f"[chunk_id={c['chunkId']}] {c['title']}"
        if c["page"]:
            header += f" ({c['page']})"
        blocks.append(f"{header}\n{c['content']}")
    return "\n\n---\n\n".join(blocks)


def _not_found(conn: sqlite3.Connection, base: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        **base,
        "source": "none",
        "title": "ไม่พบข้อมูลนี้ในระบบ",
        "lines": [reason, *repo.contact_fallback(conn)],
    }


async def answer(
    conn: sqlite3.Connection, base: dict[str, Any], question: str
) -> dict[str, Any]:
    if not config.AI_ENABLED:
        return _not_found(conn, base, "ผู้ช่วย AI ยังไม่ได้ตั้งค่ากุญแจการเข้าใช้งาน")

    chunks = retrieval.search(conn, question, limit=5)
    if not chunks:
        return _not_found(
            conn, base, "ระบบไม่พบเอกสารอ้างอิงสำหรับคำถามนี้ จึงไม่สามารถตอบได้"
        )

    allowed_ids = {c["chunkId"] for c in chunks}

    try:
        import anthropic

        response = await _get_client().messages.parse(
            model=config.ANTHROPIC_MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            output_format=AiAnswer,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"คำถามของนักศึกษา: {question}\n\n"
                        f"เอกสารอ้างอิงที่ค้นได้:\n\n{_build_context(chunks)}"
                    ),
                }
            ],
        )
        parsed: AiAnswer | None = response.parsed_output

    except anthropic.RateLimitError:
        log.warning("ผู้ช่วย AI ถูกจำกัดอัตราการเรียก")
        return _not_found(conn, base, "ผู้ช่วยตอบคำถามมีผู้ใช้งานหนาแน่น กรุณาลองใหม่อีกครั้ง")
    except anthropic.APIConnectionError:
        log.warning("เชื่อมต่อผู้ช่วย AI ไม่ได้")
        return _not_found(conn, base, "เชื่อมต่อผู้ช่วยตอบคำถามไม่ได้ในขณะนี้")
    except anthropic.APIStatusError as exc:
        log.error("ผู้ช่วย AI ตอบสถานะ %s", exc.status_code)
        return _not_found(conn, base, "ผู้ช่วยตอบคำถามขัดข้องชั่วคราว")
    except Exception:  # noqa: BLE001 — ตู้ต้องไม่ค้างเพราะผู้ช่วย AI ไม่ว่าเกิดอะไรขึ้น
        log.exception("ผู้ช่วย AI ล้มเหลวโดยไม่คาดคิด")
        return _not_found(conn, base, "ผู้ช่วยตอบคำถามขัดข้องชั่วคราว")

    if parsed is None or not parsed.found or not parsed.lines:
        return _not_found(
            conn, base, "ระบบไม่พบเอกสารอ้างอิงสำหรับคำถามนี้ จึงไม่สามารถตอบได้"
        )

    # โมเดลต้องเลือก chunk จากรายการที่ส่งไปเท่านั้น ถ้าเลขไม่อยู่ในชุดแปลว่าเชื่อถือไม่ได้
    if parsed.chunk_id not in allowed_ids:
        log.warning("โมเดลอ้าง chunk_id=%s ซึ่งไม่ได้อยู่ในบริบท", parsed.chunk_id)
        return _not_found(
            conn, base, "ระบบไม่สามารถยืนยันแหล่งที่มาของคำตอบนี้ได้ จึงไม่แสดงคำตอบ"
        )

    citation = retrieval.citation_for_chunk(conn, parsed.chunk_id)
    if citation is None:
        return _not_found(conn, base, "ระบบไม่สามารถยืนยันแหล่งที่มาของคำตอบนี้ได้")

    return {
        **base,
        "source": "ai",
        "ref": citation,
        "title": base.get("label") or question,
        "lines": parsed.lines[:4],
    }


async def answer_open(
    conn: sqlite3.Connection, question: str, base: dict[str, Any] | None = None
) -> dict[str, Any]:
    """ตอบคำถามปลายเปิดที่ผู้ใช้พูดเอง ไม่ได้มาจากปุ่มคำถามยอดนิยม

    กติกาเหมือนเดิมทุกข้อ: ต้องค้นเอกสารเจอก่อน และโมเดลเลือกได้แค่หมายเลขชิ้นเอกสาร
    ต่างกันแค่ตรงที่ข้อความคำถามมาจากเสียงพูด จึงใช้ข้อความนั้นเป็นหัวข้อคำตอบ
    """
    ctx = base or {"questionId": None, "kind": "คำถามปลายเปิด", "label": question}
    return await answer(conn, ctx, question)
