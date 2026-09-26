"""กล้อง การสแกนใบหน้า และการลงทะเบียนใบหน้า"""

from __future__ import annotations

import logging
import time
from typing import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import config, repo, thai
from ..deps import Db, StudentSession, VerifiedSession
from ..services import face as face_service
from ..services.camera import camera
from ..services.face_worker import worker

log = logging.getLogger("kiosk.face.api")

router = APIRouter(prefix="/api/face", tags=["face"])

# คุณภาพ JPEG ของภาพพรีวิว — ต่ำพอให้ Raspberry Pi ส่งทันโดยยังดูรู้เรื่อง
PREVIEW_QUALITY = 70
PREVIEW_FPS = 12


@router.get("/status")
def face_status() -> dict:
    return worker.status()


# ------------------------------------------------------------
# ภาพสดจากกล้อง
# ------------------------------------------------------------
def _mjpeg_frames() -> Iterator[bytes]:
    """ส่งภาพต่อเนื่องแบบ multipart/x-mixed-replace

    เลือก MJPEG แทน WebRTC เพราะแท็ก <img> แสดงได้เลยโดยไม่ต้องใช้จาวาสคริปต์
    และ Chromium บน Raspberry Pi ถอดรหัส JPEG ได้เร็วกว่าถอดรหัสวิดีโอ
    """
    import cv2

    last_seq = -1
    min_interval = 1.0 / PREVIEW_FPS

    while True:
        started = time.time()
        frame, seq = camera.wait_for_frame(last_seq, timeout=2.0)
        if frame is None:
            if not camera.available:
                break
            continue
        last_seq = seq

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_QUALITY])
        if not ok:
            continue

        yield (
            b"--frame\r\nContent-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(buf)).encode() + b"\r\n\r\n"
            + buf.tobytes() + b"\r\n"
        )

        # จำกัดอัตราเฟรมไม่ให้แย่งซีพียูจากการรู้จำใบหน้า
        elapsed = time.time() - started
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)


@router.get("/stream")
def stream() -> StreamingResponse:
    if not camera.available:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            camera.error or "กล้องไม่พร้อมใช้งาน",
        )
    return StreamingResponse(
        _mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache", "Pragma": "no-cache"},
    )


# ------------------------------------------------------------
# สแกนใบหน้า
# ------------------------------------------------------------
@router.post("/scan/start")
def scan_start() -> dict:
    """เริ่มหาว่าคนที่ยืนอยู่หน้าตู้คือใคร

    ผลลัพธ์ไม่ได้คืนที่นี่ แต่ส่งผ่าน WebSocket เพราะการรู้จำใช้เวลาหลายเฟรม
    """
    if not camera.available:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            camera.error or "กล้องไม่พร้อมใช้งาน",
        )
    if not face_service.engine.ready:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            face_service.engine.error or "โมเดลรู้จำใบหน้ายังไม่พร้อม",
        )
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


@router.post("/consent")
def give_consent(body: ConsentIn, conn: Db, sess: StudentSession) -> dict:
    """บันทึกความยินยอมให้ประมวลผลข้อมูลใบหน้า

    ต้องเรียกก่อนลงทะเบียนเสมอ และค่า agreed ต้องเป็น true ที่ผู้ใช้กดเอง
    ฐานข้อมูลบังคับอีกชั้นหนึ่งว่าไม่มีความยินยอมแล้วเขียนเวกเตอร์ไม่ได้
    """
    if not body.agreed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ต้องให้ความยินยอมก่อนจึงจะดำเนินการต่อได้")

    now = thai.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            """INSERT INTO consents (student_id, purpose, policy_version, granted_at, method)
               VALUES (?, 'face_recognition', ?, ?, 'kiosk_touch')""",
            (sess.student_pk, body.policyVersion or config.CONSENT_POLICY_VERSION, now),
        )
    return {"consentId": cur.lastrowid, "grantedAt": now,
            "policyVersion": body.policyVersion or config.CONSENT_POLICY_VERSION}


@router.post("/enroll/start")
def enroll_start(conn: Db, sess: StudentSession) -> dict:
    """เริ่มเก็บตัวอย่างใบหน้า

    ข้อจำกัดด้านความปลอดภัยที่บังคับไว้ที่นี่
      1. ต้องมีความยินยอมที่ยังไม่ถูกถอน
      2. ผู้ที่มีข้อมูลใบหน้าอยู่แล้วลงทะเบียนซ้ำไม่ได้

    ข้อ 2 สำคัญมาก เพราะการเข้าสู่ระบบด้วยการกรอกรหัสนักศึกษาไม่มีการยืนยันตัวตน
    ถ้าไม่กันไว้ ใครก็กรอกรหัสของผู้อื่นแล้วลงทะเบียนใบหน้าตัวเองทับได้
    ผู้ที่ต้องการลงทะเบียนใหม่ต้องไปลบข้อมูลเดิมที่สำนักงานสาขาก่อน
    """
    if not camera.available:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            camera.error or "กล้องไม่พร้อมใช้งาน",
        )

    existing = repo.face_status(conn, sess.student_pk)
    if existing["enrolled"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "รหัสนักศึกษานี้มีข้อมูลใบหน้าในระบบแล้ว "
            "หากต้องการลงทะเบียนใหม่ กรุณาติดต่อสำนักงานสาขาวิชาฯ",
        )

    consent = conn.execute(
        """SELECT id FROM consents
           WHERE student_id = ? AND purpose = 'face_recognition' AND revoked_at IS NULL
           ORDER BY id DESC LIMIT 1""",
        (sess.student_pk,),
    ).fetchone()
    if consent is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ยังไม่ได้บันทึกความยินยอม")

    worker.begin_enroll(sess.student_pk, consent["id"])
    return {"enrolling": True, "consentId": consent["id"]}


@router.post("/enroll/cancel")
def enroll_cancel() -> dict:
    worker.cancel_enroll()
    return {"enrolling": False}


@router.delete("/enroll")
def delete_own_face(conn: Db, sess: VerifiedSession) -> dict:
    """ทางลัดเดียวกับ DELETE /api/me/face เก็บไว้ให้ครบชุดของหน้ากล้อง"""
    from .me import delete_face_data

    return delete_face_data(conn, sess)
