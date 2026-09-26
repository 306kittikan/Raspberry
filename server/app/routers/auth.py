"""เริ่มและจบเซสชัน

หน้าเว็บบอกไม่ได้ว่า "ฉันคือใคร" — บอกได้แค่ว่ากดยืนยันผู้ที่ระบบเสนอมา
(candidateToken) หรือกรอกรหัสนักศึกษาเข้ามา
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .. import config, repo
from .. import session as session_store
from ..deps import Db, MaybeSession

router = APIRouter(prefix="/api/session", tags=["session"])


class ConfirmFaceIn(BaseModel):
    candidateToken: str


class StudentIdIn(BaseModel):
    studentId: str = Field(min_length=4, max_length=20)


def _session_payload(conn, sess: session_store.Session) -> dict:
    student = None
    if sess.student_pk is not None:
        row = repo.get_student(conn, sess.student_pk)
        if row is not None:
            student = repo.student_public(row, restricted=sess.restricted)
    return {
        "token": sess.token,
        "method": sess.method,
        "restricted": sess.restricted,
        "student": student,
    }


@router.post("/face-confirm")
def confirm_face(body: ConfirmFaceIn, conn: Db) -> dict:
    """ผู้ใช้กด "ใช่" บนหน้ายืนยันตัวตน"""
    cand = session_store.store.take_candidate(body.candidateToken)
    if cand is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="ผลการรู้จำใบหน้าหมดอายุแล้ว กรุณาสแกนใหม่",
        )
    sess = session_store.store.start(
        student_pk=cand.student_pk, restricted=False, method="face"
    )
    return {**_session_payload(conn, sess), "matchScore": round(cand.score, 4)}


@router.post("/student-id")
def login_with_student_id(body: StudentIdIn, conn: Db) -> dict:
    """โหมดกรอกรหัสนักศึกษา — ไม่มีการยืนยันตัวตน

    ใครก็กรอกรหัสของผู้อื่นได้ จึงตั้ง restricted = True
    ข้อมูลที่แสดงถูกจำกัด และเข้าหน้าจัดการข้อมูลใบหน้าไม่ได้
    """
    row = repo.find_student_by_code(conn, body.studentId)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ไม่พบรหัสนักศึกษานี้ในระบบของสาขา",
        )
    sess = session_store.store.start(
        student_pk=row["id"],
        restricted=config.KEYPAD_MODE_RESTRICTED,
        method="student_id",
    )
    return _session_payload(conn, sess)


@router.post("/anonymous")
def start_anonymous(conn: Db) -> dict:
    """ถามคำถามโดยไม่ระบุตัวตน — ตอบได้เฉพาะคำถามที่ไม่ใช่ข้อมูลส่วนบุคคล"""
    sess = session_store.store.start(
        student_pk=None, restricted=True, method="anonymous"
    )
    return _session_payload(conn, sess)


@router.post("/touch")
def keep_alive(sess: MaybeSession) -> dict:
    """ผู้ใช้ยังใช้งานอยู่ — เลื่อนเวลาออกจากระบบอัตโนมัติ"""
    return {"alive": sess is not None}


@router.delete("")
def logout(sess: MaybeSession) -> dict:
    """ออกจากระบบและล้างข้อมูลทั้งหมดของเซสชันนี้ทิ้งทันที"""
    if sess is not None:
        session_store.store.end(sess.token)
    return {"ok": True}
