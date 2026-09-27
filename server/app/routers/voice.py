"""รับเสียงจากไมโครโฟนของตู้ ถอดความ แล้วตอบคำถาม

ทำไมเบราว์เซอร์เป็นฝ่ายอัดเสียง แต่กล้องอยู่ฝั่งเซิร์ฟเวอร์
  เสียงเป็นข้อมูลเบา ส่งผ่าน WebSocket ได้สบาย และเบราว์เซอร์เข้าถึงไมโครโฟน
  ได้ง่ายกว่าตั้งค่าอุปกรณ์เสียงบนเซิร์ฟเวอร์ ต่างจากภาพวิดีโอที่หนักเกินกว่า
  จะส่งทุกเฟรมมาประมวลผลฝั่งเซิร์ฟเวอร์

ข้อมูลเสียงอยู่ในหน่วยความจำเท่านั้น ถอดความเสร็จแล้วถูกทิ้งทันที
ไม่มีการเขียนไฟล์เสียงลงดิสก์ และไม่มีการเก็บข้อความที่ถอดได้ลงฐานข้อมูล
สถิติที่บันทึกมีแค่ประเภทคำถาม ช่องทาง และแหล่งคำตอบ เหมือนการแตะปุ่ม

ลำดับข้อความบน WebSocket /ws/voice
  เบราว์เซอร์ → {"type":"start"}            เริ่มพูด
  เบราว์เซอร์ → เสียงที่ MediaRecorder อัด   (ส่งเป็น binary หลายก้อน)
  เบราว์เซอร์ → {"type":"stop"}             พูดจบ
  เซิร์ฟเวอร์ → {"state":"processing"}      กำลังถอดความ
  เซิร์ฟเวอร์ → {"state":"transcript", ...} ข้อความที่ได้ยิน (ให้ผู้ใช้ตรวจสอบ)
  เซิร์ฟเวอร์ → {"state":"answer", ...}     คำตอบพร้อมแหล่งที่มา
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import answers, config, repo
from ..deps import current_term_id, open_db
from ..services import intent, stt
from ..session import store as session_store

log = logging.getLogger("kiosk.voice")

router = APIRouter(tags=["voice"])

# กันไม่ให้เบราว์เซอร์ที่ทำงานผิดพลาดส่งเสียงไม่หยุดจนหน่วยความจำเต็ม
# เสียงบีบอัดแล้วจึงเล็กกว่า PCM มาก เผื่อไว้ 4 เท่าของอัตราบิตที่คาด
MAX_BYTES = 4 * 1024 * 1024

# สถิติเก็บแค่ว่าคำตอบมาจากไหน ไม่เก็บเนื้อหาคำถาม
# การคุยทั่วไปนับรวมเป็น AI เพราะก็คือการเรียกโมเดลเหมือนกัน
_SOURCE_LABEL = {"db": "ฐานข้อมูล", "ai": "AI", "ai_general": "AI", "none": "ไม่พบ"}


@router.get("/api/voice/status")
async def voice_status() -> dict:
    # ถามสถานะคือจังหวะที่ดีในการลองกู้ เพราะหน้าจอถามก่อนเปิดปุ่มไมโครโฟนเสมอ
    ready = await asyncio.to_thread(stt.engine.ensure_ready)
    return {
        "enabled": config.STT_ENABLED,
        "ready": ready,
        "error": stt.engine.error,
        "model": config.STT_MODEL,
    }


@router.websocket("/ws/voice")
async def voice_socket(ws: WebSocket) -> None:
    await ws.accept()
    chunks: list[bytes] = []
    total = 0
    recording = False

    try:
        while True:
            message = await ws.receive()

            if message.get("type") == "websocket.disconnect":
                break

            # ---- ก้อนเสียง ----
            if (data := message.get("bytes")) is not None:
                if not recording:
                    continue
                total += len(data)
                if total > MAX_BYTES:
                    await ws.send_json({"state": "error", "reason": "too_long"})
                    chunks.clear()
                    total = 0
                    recording = False
                    continue
                chunks.append(data)
                continue

            # ---- คำสั่งควบคุม ----
            text = message.get("text")
            if not text:
                continue
            try:
                command = json.loads(text)
            except json.JSONDecodeError:
                continue

            if command.get("type") == "start":
                chunks.clear()
                total = 0
                recording = True
                await ws.send_json({"state": "listening"})
                continue

            if command.get("type") == "stop":
                recording = False
                await _handle_utterance(ws, b"".join(chunks), command)
                chunks.clear()
                total = 0

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — ช่องเสียงล้มต้องไม่ทำให้ตู้ทั้งตู้ล่ม
        log.exception("ช่องทางเสียงขัดข้อง")
    finally:
        chunks.clear()


async def _handle_utterance(ws: WebSocket, raw: bytes, command: dict) -> None:
    if not await asyncio.to_thread(stt.engine.ensure_ready):
        await ws.send_json({"state": "error", "reason": "stt_not_ready",
                            "detail": stt.engine.error})
        return

    await ws.send_json({"state": "processing"})
    started = time.perf_counter()

    try:
        audio: np.ndarray = stt.decode(raw)
    except Exception as exc:  # noqa: BLE001 — เสียงเสียหายต้องไม่ทำให้ช่องทางเสียงตาย
        log.warning("ถอดรหัสเสียงไม่สำเร็จ: %s", exc)
        await ws.send_json({"state": "unclear", "reason": "decode_failed",
                            "answer": answers.UNCLEAR_ANSWER})
        return
    # ถอดความเป็นงานที่บล็อก จึงย้ายไปเธรดอื่นไม่ให้เซิร์ฟเวอร์หยุดตอบคำขออื่น
    result = await asyncio.to_thread(stt.engine.transcribe, audio)

    if not result["ok"]:
        await ws.send_json({
            "state": "unclear",
            "reason": result.get("reason"),
            "answer": answers.UNCLEAR_ANSWER,
        })
        return

    heard = result["text"]
    await ws.send_json({"state": "transcript", "text": heard,
                        "sttMs": round((time.perf_counter() - started) * 1000)})

    conn = open_db()
    guess = intent.match(conn, heard)
    online = bool(command.get("online", True))
    sess = session_store.get(command.get("token"))

    term_id = None
    if sess is not None and sess.student_pk is not None:
        term_id = current_term_id(conn)

    ctx = answers.AskContext(
        student_pk=sess.student_pk if sess else None,
        term_id=term_id,
        online=online,
        restricted=sess.restricted if sess else True,
        text=heard,
    )

    if guess.question_id is not None:
        answer = await answers.resolve(conn, guess.question_id, ctx)
    elif not online:
        answer = {
            "questionId": None,
            "kind": "คำถามปลายเปิด",
            "label": heard,
            "source": "none",
            "title": "ตอบคำถามนี้ขณะออฟไลน์ไม่ได้",
            "lines": [
                "คำถามนี้ต้องใช้ผู้ช่วย AI ซึ่งต้องเชื่อมต่ออินเทอร์เน็ต",
                "ตารางเรียนและกำหนดสอบยังถามได้ตามปกติ",
            ],
            "offlineBlocked": True,
        }
    else:
        # คำถามปลายเปิด — ค้นเอกสารของสาขาแล้วให้ผู้ช่วย AI ตอบ
        # ยังต้องอ้างอิงเอกสารเสมอ ถ้าค้นไม่เจอจะได้ "ไม่พบข้อมูลนี้ในระบบ"
        from ..services import assistant_ai

        answer = await assistant_ai.answer_open(conn, heard)

    latency_ms = round((time.perf_counter() - started) * 1000)
    repo.log_usage(
        conn,
        question_kind=answer.get("kind"),
        channel="เสียง",
        answer_source=_SOURCE_LABEL.get(answer.get("source")),
        latency_ms=latency_ms,
    )

    await ws.send_json({
        "state": "answer",
        "transcript": heard,
        "answer": answer,
        "intent": {"questionId": guess.question_id, "method": guess.method,
                   "confidence": guess.confidence},
        "latencyMs": latency_ms,
    })
