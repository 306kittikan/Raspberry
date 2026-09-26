"""กล้อง การสแกนใบหน้า และการลงทะเบียนใบหน้า"""

from __future__ import annotations

import logging
import time
from typing import Iterator

from fastapi import APIRouter, HTTPException, status
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
