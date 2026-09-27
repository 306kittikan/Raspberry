"""ผู้ช่วยตอบคำถาม — จุดเดียวที่ตัดสินว่าคำถามไหนไปฐานข้อมูล คำถามไหนไป AI

รับคำถามได้สามทาง และทุกทางผ่านกติกาเดียวกันหมด
  แตะ    ส่ง questionId ของปุ่มคำถามยอดนิยม
  พิมพ์  ส่ง text ที่ผู้ใช้พิมพ์ในหน้าต่างแชท
  เสียง  ส่งผ่าน /ws/voice ซึ่งถอดความแล้วเรียกตรรกะชุดเดียวกันนี้
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .. import answers, repo
from ..deps import Db, MaybeSession, current_term_id
from ..services import intent

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

# สถิติเก็บแค่ว่าคำตอบมาจากไหน ไม่เก็บเนื้อหาคำถาม
# การคุยทั่วไปนับรวมเป็น AI เพราะก็คือการเรียกโมเดลเหมือนกัน
_SOURCE_LABEL = {"db": "ฐานข้อมูล", "ai": "AI", "ai_general": "AI", "none": "ไม่พบ"}
_CHANNELS = {"แตะ", "เสียง", "พิมพ์"}

OFFLINE_OPEN_ANSWER = {
    "questionId": None,
    "kind": "คำถามปลายเปิด",
    "source": "none",
    "title": "ตอบคำถามนี้ขณะออฟไลน์ไม่ได้",
    "lines": [
        "คำถามนี้ต้องใช้ผู้ช่วย AI ซึ่งต้องเชื่อมต่ออินเทอร์เน็ต",
        "ตารางเรียนและกำหนดสอบยังถามได้ตามปกติ",
    ],
    "offlineBlocked": True,
}


class AskIn(BaseModel):
    """ส่ง questionId (ปุ่มคำถามยอดนิยม) หรือ text (พิมพ์เอง) อย่างใดอย่างหนึ่ง"""

    questionId: str | None = None
    text: str | None = Field(default=None, max_length=300)
    channel: str = "แตะ"
    online: bool = True        # หน้าเว็บรายงานสถานะเครือข่ายของตู้


@router.post("/ask")
async def ask(body: AskIn, conn: Db, sess: MaybeSession) -> dict:
    question_id = body.questionId
    typed = (body.text or "").strip()

    if not question_id and not typed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ต้องระบุคำถาม")

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

    guess = None
    if question_id:
        answer = await answers.resolve(conn, question_id, ctx)
    else:
        # ข้อความที่พิมพ์เองผ่านตัวตีความชุดเดียวกับที่ใช้กับเสียง
        # คำถามเรื่องตารางเรียน ห้องเรียน กำหนดสอบ จึงยังไปที่ฐานข้อมูลเสมอ
        # ไม่ถูกส่งให้ AI เดา ซึ่งเป็นกติกาหลักของโครงงาน
        guess = intent.match(conn, typed)
        if guess.question_id is not None:
            answer = await answers.resolve(conn, guess.question_id, ctx)
        elif not body.online:
            answer = {**OFFLINE_OPEN_ANSWER, "label": typed}
        else:
            from ..services import assistant_ai

            answer = await assistant_ai.answer_open(conn, typed)

    latency_ms = int((time.perf_counter() - started) * 1000)

    # สถิติไม่มีข้อมูลระบุตัวตน — ไม่เก็บข้อความที่ผู้ใช้พิมพ์
    # เก็บเฉพาะประเภทคำถาม ช่องทาง และแหล่งคำตอบ เหมือนการแตะปุ่มทุกประการ
    repo.log_usage(
        conn,
        question_kind=answer.get("kind"),
        channel=body.channel if body.channel in _CHANNELS else None,
        answer_source=_SOURCE_LABEL.get(answer.get("source")),
        latency_ms=latency_ms,
    )

    result = {"answer": answer, "latencyMs": latency_ms}
    if guess is not None:
        result["intent"] = {
            "questionId": guess.question_id,
            "method": guess.method,
            "confidence": guess.confidence,
        }
    return result


@router.get("/unclear")
def unclear() -> dict:
    """คำตอบมาตรฐานเมื่อฟังเสียงไม่ชัด"""
    return {"answer": answers.UNCLEAR_ANSWER}
