"""ผู้ช่วยตอบคำถาม — จุดเดียวที่ตัดสินว่าคำถามไหนไปฐานข้อมูล คำถามไหนไป AI"""

from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel

from .. import answers, repo
from ..deps import Db, MaybeSession, current_term_id

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_SOURCE_LABEL = {"db": "ฐานข้อมูล", "ai": "AI", "none": "ไม่พบ"}


class AskIn(BaseModel):
    questionId: str
    channel: str = "แตะ"       # 'แตะ' | 'เสียง'
    online: bool = True        # หน้าเว็บรายงานสถานะเครือข่ายของตู้


@router.post("/ask")
async def ask(body: AskIn, conn: Db, sess: MaybeSession) -> dict:
    started = time.perf_counter()

    term_id = None
    if sess is not None and sess.student_pk is not None:
        term_id = current_term_id(conn)

    ctx = answers.AskContext(
        student_pk=sess.student_pk if sess else None,
        term_id=term_id,
        online=body.online,
        restricted=sess.restricted if sess else True,
    )
    answer = await answers.resolve(conn, body.questionId, ctx)
    latency_ms = int((time.perf_counter() - started) * 1000)

    # สถิติไม่มีข้อมูลระบุตัวตน — เก็บเฉพาะประเภทคำถาม ช่องทาง และแหล่งคำตอบ
    repo.log_usage(
        conn,
        question_kind=answer.get("kind"),
        channel=body.channel if body.channel in {"แตะ", "เสียง"} else None,
        answer_source=_SOURCE_LABEL.get(answer.get("source")),
        latency_ms=latency_ms,
    )

    return {"answer": answer, "latencyMs": latency_ms}


@router.get("/unclear")
def unclear() -> dict:
    """คำตอบมาตรฐานเมื่อฟังเสียงไม่ชัด"""
    return {"answer": answers.UNCLEAR_ANSWER}
