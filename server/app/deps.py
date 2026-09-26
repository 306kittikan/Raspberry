"""ตัวช่วยที่ทุก router ใช้ร่วมกัน"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from . import db as db_module
from . import repo, session

_conn: sqlite3.Connection | None = None


def open_db() -> sqlite3.Connection:
    """เปิดการเชื่อมต่อครั้งเดียวตลอดอายุกระบวนการ

    SQLite ทำงานแบบไฟล์เดียวและตู้มีผู้ใช้ทีละคน การใช้การเชื่อมต่อเดียว
    จึงเพียงพอและหลีกเลี่ยงปัญหาล็อกไฟล์บนแฟลชไดรฟ์
    """
    global _conn
    if _conn is None:
        _conn = db_module.connect()
        db_module.init_db(_conn)
    return _conn


def close_db() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def get_db() -> sqlite3.Connection:
    return open_db()


Db = Annotated[sqlite3.Connection, Depends(get_db)]


def get_session(
    x_kiosk_session: Annotated[str | None, Header()] = None,
) -> session.Session | None:
    """เซสชันปัจจุบัน (ถ้ามี) — ไม่บังคับว่าต้องยืนยันตัวตนแล้ว"""
    return session.store.touch(x_kiosk_session) if x_kiosk_session else None


MaybeSession = Annotated[session.Session | None, Depends(get_session)]


def require_student(sess: MaybeSession) -> session.Session:
    """บังคับว่าต้องมีตัวตนผูกกับเซสชัน ใช้กับทุกเส้นทางที่คืนข้อมูลส่วนบุคคล"""
    if sess is None or sess.student_pk is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ต้องยืนยันตัวตนก่อนจึงจะดูข้อมูลนี้ได้",
        )
    return sess


StudentSession = Annotated[session.Session, Depends(require_student)]


def require_verified_student(sess: StudentSession) -> session.Session:
    """เข้มกว่า require_student — ต้องยืนยันด้วยใบหน้าเท่านั้น

    โหมดกรอกรหัสนักศึกษาไม่มีการยืนยันตัวตน จึงห้ามใช้จัดการข้อมูลใบหน้า
    มิฉะนั้นใครก็กรอกรหัสผู้อื่นแล้วลบข้อมูลใบหน้าของคนนั้นทิ้งได้
    """
    if sess.restricted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ต้องยืนยันตัวตนด้วยใบหน้าก่อนจึงจะจัดการข้อมูลใบหน้าได้",
        )
    return sess


VerifiedSession = Annotated[session.Session, Depends(require_verified_student)]


def current_term_id(conn: sqlite3.Connection) -> int:
    term = repo.get_current_term(conn)
    if term is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ยังไม่ได้กำหนดภาคการศึกษาปัจจุบัน",
        )
    return term["id"]
