"""ข้อมูลส่วนบุคคล — ทุกเส้นทางในไฟล์นี้ต้องมีเซสชันที่ผูกกับตัวตนแล้ว"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from .. import config, repo, thai
from ..deps import Db, StudentSession, VerifiedSession, current_term_id

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("")
def me(conn: Db, sess: StudentSession) -> dict:
    row = repo.get_student(conn, sess.student_pk)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบข้อมูลนักศึกษา")
    return repo.student_public(row, restricted=sess.restricted)


@router.get("/schedule")
def schedule(conn: Db, sess: StudentSession) -> dict:
    """ตารางเรียนทั้งหมด พร้อมมุมมองวันนี้ ทั้งสัปดาห์ และคาบถัดไป

    คำนวณที่เซิร์ฟเวอร์ทั้งหมด เพื่อให้คำตอบเหมือนกันไม่ว่าจะเข้าทางหน้าจอหรือผู้ช่วย
    """
    term_id = current_term_id(conn)
    now = thai.now()
    items = repo.get_schedule(conn, sess.student_pk, term_id)

    return {
        "hasSchedule": bool(items),
        "today": repo.classes_today(items, now),
        "week": {str(day): rows for day, rows in repo.classes_by_week(items).items()},
        "nextClass": repo.find_next_class(items, now),
        "todayLabel": thai.format_full_date(now.date()),
    }


@router.get("/exams")
def exams(conn: Db, sess: StudentSession) -> dict:
    term_id = current_term_id(conn)
    today = thai.now().date().isoformat()
    rows = repo.get_exams(conn, sess.student_pk, term_id)
    return {
        "exams": rows,
        "upcoming": [e for e in rows if e["dateISO"] >= today],
    }


@router.get("/face")
def face_status(conn: Db, sess: VerifiedSession) -> dict:
    status_ = repo.face_status(conn, sess.student_pk)
    return {**status_, "policyVersion": config.CONSENT_POLICY_VERSION}


@router.delete("/face")
def delete_face_data(conn: Db, sess: VerifiedSession) -> dict:
    """ลบข้อมูลใบหน้าของตนเอง (สิทธิตาม พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคลฯ)

    บันทึกเวลาถอนความยินยอมไว้เป็นหลักฐาน แล้วลบเวกเตอร์ทิ้งจริง
    ไม่ใช่แค่ทำเครื่องหมายว่าลบแล้ว
    """
    now = thai.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            UPDATE consents SET revoked_at = ?
            WHERE student_id = ? AND purpose = 'face_recognition' AND revoked_at IS NULL
            """,
            (now, sess.student_pk),
        )
        cur = conn.execute(
            "DELETE FROM face_embeddings WHERE student_id = ?", (sess.student_pk,)
        )
        deleted = cur.rowcount

    return {
        "deleted": deleted,
        "revokedAt": now,
        "message": "ลบข้อมูลใบหน้าของคุณออกจากระบบเรียบร้อยแล้ว",
    }
