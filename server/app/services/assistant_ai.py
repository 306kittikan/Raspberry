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
from typing import Any, Literal

from pydantic import BaseModel, Field

from .. import config, repo, thai
from . import llm, retrieval

log = logging.getLogger("kiosk.ai")

_client: Any = None


class _Health:
    """สถานะล่าสุดของผู้ช่วย AI ไว้ให้เจ้าหน้าที่ดูว่าใช้งานได้จริงหรือไม่

    ค่า AI_ENABLED บอกได้แค่ว่า "ตั้งค่ากุญแจไว้แล้ว" ซึ่งไม่เหมือนกับ
    "เรียกใช้ได้จริง" กุญแจอาจหมดอายุ เครดิตอาจหมด หรือเน็ตอาจใช้ไม่ได้
    ถ้าไม่เก็บไว้ ตู้จะตอบ "ไม่พบข้อมูล" เงียบ ๆ ทุกคำถามโดยไม่มีใครรู้สาเหตุ
    """

    def __init__(self) -> None:
        self.calls = 0
        self.failures = 0
        self.last_error: str | None = None
        self.last_ok_at: str | None = None
        self.input_tokens = 0
        self.output_tokens = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": config.AI_ENABLED,
            "provider": llm.provider(),
            "model": llm.model_name(),
            "calls": self.calls,
            "failures": self.failures,
            "lastError": self.last_error,
            "lastOkAt": self.last_ok_at,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
        }


health = _Health()


SYSTEM_PROMPT = """\
คุณคือผู้ช่วยของตู้บริการข้อมูล สาขาวิชาวิทยาการคอมพิวเตอร์ \
คณะวิทยาศาสตร์ มหาวิทยาลัยแม่โจ้ ผู้ถามคือนักศึกษาที่ยืนอยู่หน้าตู้
คุยกับเขาอย่างเป็นมิตรและเป็นกันเอง เหมือนรุ่นพี่ที่นั่งอยู่ประจำจุดบริการ

คำถามมีสองแบบ และต้องแยกให้ขาดจากกัน

แบบที่ 1 — เรื่องของสาขา มหาวิทยาลัย หลักสูตร รายวิชา อาจารย์ อาคาร
ค่าเทอม ระเบียบ กำหนดการ หรืออะไรก็ตามที่เป็นข้อเท็จจริงของที่นี่
  ตอบได้เฉพาะสิ่งที่ปรากฏในเอกสารอ้างอิงที่ให้มาเท่านั้น
  ตั้ง answer_type = "department" แล้วระบุ chunk_id ของชิ้นที่ใช้ตอบ
  **ห้ามใช้ความรู้ทั่วไปของคุณมาเติมแม้แต่ประโยคเดียว**
  ถ้าเอกสารไม่มีคำตอบ ให้ตั้ง answer_type = "none"
  ห้ามเลี่ยงไปตอบแบบ "general" เด็ดขาด เพราะนักศึกษาจะเข้าใจว่าเป็นข้อมูลจริงของสาขา
  แล้วอาจเดินไปผิดตึกหรือพลาดกำหนดส่งเอกสาร

แบบที่ 2 — เรื่องทั่วไปที่ไม่ใช่ข้อเท็จจริงของที่นี่
  เช่น ทักทาย ถามสารทุกข์สุกดิบ ขอกำลังใจ ถามความรู้ทั่วไป
  ให้อธิบายแนวคิดการเขียนโปรแกรม เล่าเรื่องสนุก ๆ หรือชวนคุยเล่น
  ตอบได้ตามปกติด้วยความรู้ของคุณเอง ตั้ง answer_type = "general" และไม่ต้องมี chunk_id

เรื่องที่ห้ามตอบเสมอ
- ตารางเรียน ห้องเรียน และกำหนดสอบของนักศึกษา
  ระบบดึงจากฐานข้อมูลเองอยู่แล้ว ถ้าถูกถามให้ตั้ง answer_type = "none"
- ข้อมูลส่วนบุคคลของนักศึกษาคนอื่น ให้ตั้ง answer_type = "none"

สิ่งที่คุณไม่มีทางรู้ ห้ามเดาเป็นตัวเลขหรือข้อเท็จจริงเด็ดขาด
เช่น ราคาสินค้าวันนี้ พยากรณ์อากาศ ผลการแข่งขัน หรือข่าวล่าสุด
ให้บอกตามตรงว่าไม่ทราบ แล้วแนะนำแหล่งที่ควรไปดูแทน
วันเวลาปัจจุบันมีให้ในข้อความด้านล่าง ให้ใช้ค่านั้น ห้ามเดาเอง

รูปแบบคำตอบ
- เขียนเป็นภาษาไทย แยกเป็นข้อสั้น ๆ 1–4 ข้อ ข้อละไม่เกินหนึ่งบรรทัด
- ผู้ใช้ยืนอ่านจากระยะ 50–80 ซม. จึงต้องกระชับ อ่านจบได้ในไม่กี่วินาที
- ทักทายหรือคุยเล่นให้ตอบสั้น ๆ หนึ่งถึงสองบรรทัดพอ
- ห้ามเขียนชื่อเอกสารอ้างอิงลงใน lines ระบบใส่ให้เองจากฐานข้อมูล\
"""


class AiAnswer(BaseModel):
    """โครงคำตอบที่บังคับให้โมเดลส่งกลับ

    answer_type เป็นหัวใจของการออกแบบนี้ เพราะมันคือสิ่งที่ตัดสินว่า
    หน้าจอจะติดป้ายว่า "ข้อมูลของสาขา" หรือ "ความรู้ทั่วไป"
    นักศึกษาต้องแยกออกเสมอว่าคำตอบไหนเชื่อถือได้ในฐานะข้อมูลทางการ
    """

    answer_type: Literal["department", "general", "none"] = Field(
        description=(
            "department = ตอบจากเอกสารของสาขา ต้องมี chunk_id · "
            "general = คุยทั่วไปด้วยความรู้ของคุณเอง ไม่ต้องมี chunk_id · "
            "none = ตอบไม่ได้"
        )
    )
    chunk_id: int | None = Field(
        default=None, description="หมายเลขชิ้นเอกสารที่ใช้ตอบ ต้องมาจากรายการที่ให้มาเท่านั้น"
    )
    lines: list[str] = Field(
        default_factory=list, description="คำตอบภาษาไทย 1–4 ข้อ ข้อละหนึ่งบรรทัด"
    )


def _build_context(chunks: list[dict[str, Any]]) -> str:
    blocks = []
    for c in chunks:
        header = f"[chunk_id={c['chunkId']}] {c['title']}"
        if c["page"]:
            header += f" ({c['page']})"
        blocks.append(f"{header}\n{c['content']}")
    return "\n\n---\n\n".join(blocks)


def _not_found(conn: sqlite3.Connection, base: dict[str, Any], reason: str) -> dict[str, Any]:
    """คำตอบมาตรฐานเมื่อตอบไม่ได้ — บอกเหตุผลและช่องทางติดต่อ ไม่เดาคำตอบ"""
    return {
        **base,
        "source": "none",
        "title": "ไม่พบข้อมูลนี้ในระบบ",
        "lines": [reason, *repo.contact_fallback(conn)],
    }


# ข้อความที่ผู้ใช้เห็น แยกตามสาเหตุ — ผู้ใช้ไม่ต้องรู้ว่าใครเป็นผู้ให้บริการ
# แต่ต้องรู้ว่าควรลองใหม่ หรือควรไปหาเจ้าหน้าที่
_REASON = {
    "rate_limit": "ผู้ช่วยตอบคำถามใช้งานครบโควตาแล้ว กรุณาลองใหม่ภายหลัง",
    "unavailable": "ผู้ช่วยตอบคำถามมีผู้ใช้งานหนาแน่น กรุณาลองใหม่อีกครั้ง",
    "auth": "ผู้ช่วยตอบคำถามยังไม่พร้อมใช้งาน กรุณาแจ้งเจ้าหน้าที่",
    "no_key": "ผู้ช่วยตอบคำถามยังไม่ได้ตั้งค่า กรุณาแจ้งเจ้าหน้าที่",
    "connection": "เชื่อมต่อผู้ช่วยตอบคำถามไม่ได้ในขณะนี้",
    "api_error": "ผู้ช่วยตอบคำถามขัดข้องชั่วคราว",
}


def _fail(
    conn: sqlite3.Connection,
    base: dict[str, Any],
    code: str,
    reason: str,
    *,
    trace: bool = True,
) -> dict[str, Any]:
    """บันทึกความล้มเหลวไว้ให้ตรวจสอบได้ แล้วตอบแบบไม่เดาคำตอบ

    เก็บรหัสสาเหตุไว้ เพราะ "ตอบไม่ได้" มีหลายแบบที่แก้คนละทาง
    กุญแจหมดอายุกับเน็ตหลุดดูเหมือนกันบนหน้าจอ แต่ต่างกันสิ้นเชิงสำหรับเจ้าหน้าที่
    """
    health.failures += 1
    health.last_error = code
    if trace:
        log.warning("ผู้ช่วย AI ตอบไม่ได้: %s", code)
    return _not_found(conn, base, reason)


async def answer(
    conn: sqlite3.Connection, base: dict[str, Any], question: str
) -> dict[str, Any]:
    if not config.AI_ENABLED:
        return _not_found(conn, base, "ผู้ช่วย AI ยังไม่ได้ตั้งค่ากุญแจการเข้าใช้งาน")

    # ค้นเอกสารก่อนเสมอ แต่ค้นไม่เจอก็ยังเรียกโมเดลได้
    # เพราะคำถามอาจเป็นการทักทายหรือคุยเล่น ซึ่งไม่ต้องใช้เอกสารอยู่แล้ว
    # แลกกับการที่คำถามนอกเรื่องจะเสียค่าเรียกโมเดลหนึ่งครั้ง
    chunks = retrieval.search(conn, question, limit=config.AI_CONTEXT_CHUNKS)
    allowed_ids = {c["chunkId"] for c in chunks}
    health.calls += 1

    try:
        result = await llm.complete(
            system=SYSTEM_PROMPT,
            schema=AiAnswer,
            prompt=(
                # ตู้รู้เวลาอยู่แล้ว แต่โมเดลไม่รู้ ถ้าไม่บอกมันจะเดา
                # ซึ่งเคยเดาว่าเป็นสิบโมงเช้าทั้งที่เป็นบ่ายสอง
                f"ขณะนี้ {thai.format_datetime(thai.now())} (เวลาประเทศไทย)\n\n"
                f"คำถามของนักศึกษา: {question}\n\n"
                + (
                    f"เอกสารอ้างอิงที่ค้นได้:\n\n{_build_context(chunks)}"
                    if chunks
                    else "ไม่พบเอกสารอ้างอิงสำหรับคำถามนี้ "
                         "ถ้าเป็นคำถามเรื่องของสาขาให้ตั้ง answer_type = none"
                )
            ),
        )
    except llm.LlmError as exc:
        return _fail(conn, base, exc.code, _REASON.get(exc.code, _REASON["api_error"]))
    except Exception as exc:  # noqa: BLE001 — ตู้ต้องไม่ค้างเพราะผู้ช่วย AI ไม่ว่าเกิดอะไรขึ้น
        log.exception("ผู้ช่วย AI ล้มเหลวโดยไม่คาดคิด")
        return _fail(conn, base, exc.__class__.__name__,
                     _REASON["api_error"], trace=False)

    health.input_tokens += result.input_tokens
    health.output_tokens += result.output_tokens

    # โมเดลอาจปฏิเสธคำถามเองด้วยเหตุผลด้านความปลอดภัย ต้องตรวจก่อนอ่านคำตอบ
    if result.refused:
        return _fail(conn, base, "refusal", "ผู้ช่วยตอบคำถามไม่สามารถตอบคำถามนี้ได้")

    parsed: AiAnswer | None = result.parsed
    if parsed is None or not parsed.lines or parsed.answer_type == "none":
        return _not_found(
            conn, base, "ระบบไม่พบเอกสารอ้างอิงสำหรับคำถามนี้ จึงไม่สามารถตอบได้"
        )

    health.last_ok_at = thai.now().isoformat(timespec="seconds")

    # ---- คุยทั่วไป: ตอบได้ แต่ต้องไม่ถูกเข้าใจว่าเป็นข้อมูลของสาขา ----
    if parsed.answer_type == "general":
        return {
            **base,
            "source": "ai_general",
            "title": base.get("label") or question,
            "lines": parsed.lines[:4],
        }

    # ---- ข้อเท็จจริงของสาขา: ต้องพิสูจน์ที่มาได้ทุกครั้ง ----
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
