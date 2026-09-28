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
from ..services import reg_lookup

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

    # ตรวจสถานภาพอีกครั้งตรงจุดที่เปิดเซสชันจริง
    # ตัวรู้จำใบหน้าตรวจให้แล้วชั้นหนึ่ง แต่โทเค็นมีอายุถึง 45 วินาที
    # และอาจถูกสร้างจากทางอื่น (เช่น เส้นทางจำลอง) การตรวจที่ต้นทางอย่างเดียว
    # จึงไม่พอ ต้องตรวจที่จุดที่ให้สิทธิ์เข้าถึงข้อมูลส่วนบุคคลด้วยเสมอ
    student = repo.get_student(conn, cand.student_pk)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="ไม่พบข้อมูลนักศึกษา กรุณาสแกนใหม่",
        )
    if not repo.is_active(student):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=repo.status_message(student),
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
    # ผู้ที่ลาออกหรือพ้นสภาพไม่ควรเห็นตารางเรียนของภาคการศึกษาปัจจุบัน
    if not repo.is_active(row):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=repo.status_message(row),
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
def logout(conn: Db, sess: MaybeSession) -> dict:
    """ออกจากระบบและล้างข้อมูลทั้งหมดของเซสชันนี้ทิ้งทันที"""
    if sess is not None:
        # ตารางเรียนที่ดึงสดมาจากระบบทะเบียนอยู่ในหน่วยความจำเท่านั้น
        # แต่ต้องลบทันทีที่ผู้ใช้เดินจากไป ไม่ใช่รอให้หมดอายุเอง
        # เพราะคนถัดไปมายืนที่ตู้เครื่องเดียวกัน
        if sess.student_pk is not None:
            student = repo.get_student(conn, sess.student_pk)
            if student is not None:
                reg_lookup.forget(student["student_id"])
        session_store.store.end(sess.token)
    return {"ok": True}
