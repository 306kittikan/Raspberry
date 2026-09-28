"""กล้อง การสแกนใบหน้า และการลงทะเบียนใบหน้า"""

from __future__ import annotations

import logging
import threading
import time
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import sqlite3

from .. import config, repo, thai
from ..deps import Db, MaybeSession, VerifiedSession
from ..session import store as session_store
from ..services import face as face_service
from ..services.camera import camera
from ..services.face_worker import worker

log = logging.getLogger("kiosk.face.api")

router = APIRouter(prefix="/api/face", tags=["face"])

# คุณภาพ JPEG ของภาพพรีวิว — ต่ำพอให้ Raspberry Pi ส่งทันโดยยังดูรู้เรื่อง
# อายุสูงสุดของภาพสดหนึ่งสาย หน้าจอจะขอสายใหม่เองเมื่อถูกตัด
STREAM_MAX_SECONDS = 180.0

PREVIEW_QUALITY = 70
PREVIEW_FPS = 12

# จำนวนภาพสดที่เปิดพร้อมกันได้
#
# ภาพสดหนึ่งสายกินเธรดของเซิร์ฟเวอร์เป็นระยะ ๆ ตลอดเวลาที่เปิดอยู่
# และเซิร์ฟเวอร์มีเธรดจำกัด เส้นทางอื่นทั้งหมดใช้เธรดชุดเดียวกันนี้
# ถ้าภาพสดค้างสะสมไปเรื่อย ๆ ตู้จะเริ่มตอบช้าลงแล้วหยุดตอบไปเลย
# ซึ่งเห็นเป็นอาการ "ใช้ไปสักพักแล้วค้าง"
#
# ตู้จริงมีหน้าจอเดียวและเปิดภาพสดได้ทีละหนึ่งถึงสองที่
# แต่ตอนสลับหน้า สายเก่ากับสายใหม่ซ้อนกันได้ชั่วครู่ และเบราว์เซอร์
# บางครั้งขอสายใหม่ก่อนที่สายเก่าจะถูกปิด จึงต้องเผื่อไว้มากกว่าที่ใช้จริง
# แน่นเกินไปจะเห็นเป็นภาพกล้องกะพริบตอนเปลี่ยนหน้า
MAX_STREAMS = 8

_stream_lock = threading.Lock()
_active_streams = 0


def active_streams() -> int:
    with _stream_lock:
        return _active_streams


@router.get("/status")
def face_status() -> dict:
    return worker.status()


# ------------------------------------------------------------
# ภาพสดจากกล้อง
# ------------------------------------------------------------
async def _mjpeg_frames(request: Request) -> AsyncIterator[bytes]:
    """ส่งภาพต่อเนื่องแบบ multipart/x-mixed-replace

    เลือก MJPEG แทน WebRTC เพราะแท็ก <img> แสดงได้เลยโดยไม่ต้องใช้จาวาสคริปต์
    และ Chromium บน Raspberry Pi ถอดรหัส JPEG ได้เร็วกว่าถอดรหัสวิดีโอ

    เขียนเป็นฟังก์ชันแบบ async เพื่อให้ถามได้ว่าอีกฝั่งยังดูอยู่ไหม
    ตอนเป็นฟังก์ชันธรรมดา เซิร์ฟเวอร์ไม่มีทางรู้ว่าเบราว์เซอร์ปิดไปแล้ว
    จึงส่งภาพต่อไปเรื่อย ๆ ตลอดอายุของเซิร์ฟเวอร์
    สายที่ตายแล้วสะสมไปกินเธรดจนเส้นทางอื่นเริ่มช้าลงแล้วหยุดตอบ
    ซึ่งเห็นเป็นอาการ "ใช้ไปสักพักแล้วค้าง"

    งานที่บล็อก คือรอเฟรมกับเข้ารหัส JPEG ถูกโยนไปทำในเธรดอื่น
    ไม่ให้ไปหยุดลูปหลักของเซิร์ฟเวอร์ซึ่งต้องคอยรับคำขออื่นอยู่
    """
    import anyio
    import cv2

    global _active_streams
    with _stream_lock:
        _active_streams += 1

    state = {"seq": -1}
    min_interval = 1.0 / PREVIEW_FPS
    # เพดานอายุเผื่อกรณีที่การตรวจจับการตัดการเชื่อมต่อไม่ทำงาน
    # หน้าจอที่ยังดูอยู่จะขอสายใหม่ให้เองโดยผู้ใช้ไม่รู้สึก
    deadline = time.time() + STREAM_MAX_SECONDS

    def grab() -> bytes | None:
        frame, seq = camera.wait_for_frame(state["seq"], timeout=2.0)
        if frame is None:
            return None
        state["seq"] = seq
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_QUALITY])
        return buf.tobytes() if ok else None

    try:
        while True:
            started = time.time()
            if started > deadline or await request.is_disconnected():
                break
            if not camera.available:
                break

            jpeg = await anyio.to_thread.run_sync(grab)
            if jpeg is None:
                continue

            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                + jpeg + b"\r\n"
            )

            # จำกัดอัตราเฟรมไม่ให้แย่งซีพียูจากการรู้จำใบหน้า
            elapsed = time.time() - started
            if elapsed < min_interval:
                await anyio.sleep(min_interval - elapsed)
    finally:
        # ต้องลดตัวนับเสมอ ไม่ว่าจะจบเพราะหมดเวลา กล้องหาย
        # หรือเบราว์เซอร์ตัดการเชื่อมต่อกลางคัน
        with _stream_lock:
            _active_streams -= 1


@router.get("/stream")
def stream(request: Request) -> StreamingResponse:
    if not camera.available:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            camera.error or "กล้องไม่พร้อมใช้งาน",
        )
    if active_streams() >= MAX_STREAMS:
        # ปฏิเสธดีกว่าปล่อยให้สะสมจนตู้ทั้งตู้ตอบไม่ได้
        # หน้าจอจะขึ้นว่ากล้องไม่พร้อม ซึ่งยังใช้การกรอกรหัสนักศึกษาต่อได้
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "มีภาพสดเปิดอยู่มากเกินไป",
        )
    return StreamingResponse(
        _mjpeg_frames(request),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache", "Pragma": "no-cache"},
    )


def _require_camera() -> None:
    """ต้องมีกล้องที่ทำงานอยู่จริงก่อนจึงเริ่มสแกนหรือถ่ายใบหน้าได้

    ตรวจว่าลูปประมวลผลภาพยังทำงานอยู่จริง ไม่ใช่แค่ว่าเปิดกล้องสำเร็จตอนเปิดเครื่อง
    เพราะลูปกล้องอาจตายไปแล้วระหว่างทาง เช่น หน่วยความจำไม่พอ
    ถ้าปล่อยผ่าน หน้าจอจะขึ้นว่ากำลังสแกนแล้วรอผลที่ไม่มีวันมา
    """
    ok, detail = worker.ensure_running()
    if not ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail or "กล้องไม่พร้อมใช้งาน")
    if not face_service.engine.ready:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            face_service.engine.error or "โมเดลรู้จำใบหน้ายังไม่พร้อม",
        )


# ------------------------------------------------------------
# สแกนใบหน้า
# ------------------------------------------------------------
@router.post("/scan/start")
def scan_start() -> dict:
    """เริ่มหาว่าคนที่ยืนอยู่หน้าตู้คือใคร

    ผลลัพธ์ไม่ได้คืนที่นี่ แต่ส่งผ่าน WebSocket เพราะการรู้จำใช้เวลาหลายเฟรม
    """
    _require_camera()
    worker.begin_scan()
    return {"scanning": True, "timeoutSeconds": 10}


@router.post("/scan/stop")
def scan_stop() -> dict:
    worker.end_scan()
    return {"scanning": False}


# ------------------------------------------------------------
# ความยินยอมและการลงทะเบียนใบหน้า
# ------------------------------------------------------------
class ConsentIn(BaseModel):
    agreed: bool
    policyVersion: str | None = None


@router.post("/enroll/begin")
def enroll_begin(body: ConsentIn) -> dict:
    """ขั้นที่ 1: ให้ความยินยอมแล้วเริ่มถ่ายใบหน้าทันที

    ยังไม่ต้องรู้ว่าเป็นใคร ผู้ใช้กรอกรหัสนักศึกษาทีหลัง
    เพราะกล้องจ่ออยู่ที่หน้าเขาอยู่แล้ว ถ่ายเลยจึงเป็นธรรมชาติกว่า
    และเวลาที่เสียไปกับการกรอกรหัสก็ไม่ต้องให้ยืนค้างอยู่หน้ากล้อง

    ความยินยอมยังต้องมาก่อนการถ่ายเสมอ ตามที่ พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคลฯ
    มาตรา 26 กำหนดไว้สำหรับข้อมูลชีวภาพ
    เวลาที่กดยินยอมถูกจำไว้แล้วบันทึกลงฐานข้อมูลพร้อมเวกเตอร์ในขั้นสุดท้าย
    """
    if not body.agreed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ต้องให้ความยินยอมก่อนจึงจะถ่ายใบหน้าได้")
    _require_camera()

    policy = body.policyVersion or config.CONSENT_POLICY_VERSION
    worker.begin_enroll(consent_at=thai.now(), policy_version=policy)
    return {"capturing": True, "policyVersion": policy}


class CompleteEnrollIn(BaseModel):
    pendingToken: str
    studentId: str | None = None


@router.post("/enroll/complete")
def enroll_complete(body: CompleteEnrollIn, conn: Db, sess: MaybeSession) -> dict:
    """ขั้นที่ 2: บอกว่าใบหน้าที่เพิ่งถ่ายเป็นของนักศึกษาคนใด

    ถึงขั้นนี้เท่านั้นที่เวกเตอร์ถูกเขียนลงดิสก์ พร้อมกับบันทึกความยินยอม
    ในรายการเดียวกัน ถ้าขั้นใดขั้นหนึ่งล้มเหลวจะไม่มีอะไรถูกบันทึกเลย
    """
    pending = session_store.take_enrollment(body.pendingToken)
    if pending is None:
        raise HTTPException(
            status.HTTP_410_GONE,
            "ข้อมูลใบหน้าที่ถ่ายไว้หมดอายุแล้ว กรุณาถ่ายใหม่อีกครั้ง",
        )

    # รู้ตัวตนได้สองทาง: จากเซสชันที่ยืนยันแล้ว หรือจากรหัสที่เพิ่งกรอก
    if sess is not None and sess.student_pk is not None:
        student = repo.get_student(conn, sess.student_pk)
    elif body.studentId:
        student = repo.find_student_by_code(conn, body.studentId)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ต้องระบุรหัสนักศึกษา")

    if student is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "ไม่พบรหัสนักศึกษานี้ในระบบของสาขา"
        )

    # ผู้ที่ไม่ได้เป็นนักศึกษาแล้วไม่ควรฝากข้อมูลชีวภาพไว้กับสาขา
    if not repo.is_active(student):
        raise HTTPException(status.HTTP_403_FORBIDDEN, repo.status_message(student))

    # รหัสที่มีข้อมูลใบหน้าอยู่แล้วลงทะเบียนซ้ำไม่ได้
    # เพราะการกรอกรหัสไม่ได้ยืนยันตัวตน ถ้าไม่กันไว้ใครก็ลงทะเบียนทับของผู้อื่นได้
    if repo.face_status(conn, student["id"])["enrolled"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "รหัสนักศึกษานี้มีข้อมูลใบหน้าในระบบแล้ว "
            "หากต้องการลงทะเบียนใหม่ กรุณาติดต่อสำนักงานสาขาวิชาฯ",
        )

    now = thai.now().isoformat(timespec="seconds")
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO consents
                       (student_id, purpose, policy_version, granted_at, method)
                   VALUES (?, 'face_recognition', ?, ?, 'kiosk_touch')""",
                (student["id"], pending.policy_version,
                 pending.consent_at.isoformat(timespec="seconds")),
            )
            conn.execute(
                """INSERT INTO face_embeddings
                       (student_id, consent_id, vector, dim, model, quality, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student["id"], cur.lastrowid, face_service.to_blob(pending.vector),
                 face_service.EMBEDDING_DIM, face_service.MODEL_TAG, pending.quality, now),
            )
    except sqlite3.Error as exc:
        log.warning("บันทึกข้อมูลใบหน้าไม่สำเร็จ: %s", exc)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "บันทึกข้อมูลใบหน้าไม่สำเร็จ"
        ) from exc

    log.info("ลงทะเบียนใบหน้าสำเร็จ: %s (quality=%.3f)", student["name"], pending.quality)

    # เปิดเซสชันให้ใช้งานต่อได้เลย
    # ยังเป็นเซสชันแบบจำกัดเหมือนการกรอกรหัส เพราะรหัสที่กรอกยังไม่ได้ถูกยืนยัน
    # ครั้งหน้าเมื่อสแกนใบหน้าแล้วระบบจำได้ จะได้เซสชันเต็มเอง
    new_sess = session_store.start(
        student_pk=student["id"],
        restricted=config.KEYPAD_MODE_RESTRICTED,
        method="face_enroll",
    )
    return {
        "token": new_sess.token,
        "method": new_sess.method,
        "restricted": new_sess.restricted,
        "student": repo.student_public(student, restricted=new_sess.restricted),
        "quality": round(pending.quality, 3),
    }


class CancelEnrollIn(BaseModel):
    pendingToken: str | None = None


@router.post("/enroll/cancel")
def enroll_cancel(body: CancelEnrollIn | None = None) -> dict:
    """ยกเลิกกลางคัน — ทิ้งใบหน้าที่พักไว้ทันที ไม่รอหมดอายุ"""
    worker.cancel_enroll()
    session_store.drop_enrollment(body.pendingToken if body else None)
    return {"capturing": False}


@router.delete("/enroll")
def delete_own_face(conn: Db, sess: VerifiedSession) -> dict:
    """ทางลัดเดียวกับ DELETE /api/me/face เก็บไว้ให้ครบชุดของหน้ากล้อง"""
    from .me import delete_face_data

    return delete_face_data(conn, sess)
