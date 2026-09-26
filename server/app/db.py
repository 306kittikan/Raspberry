"""การเชื่อมต่อฐานข้อมูล SQLite"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def connect(path: Path | None = None) -> sqlite3.Connection:
    """เปิดการเชื่อมต่อพร้อมค่าตั้งที่ระบบต้องใช้เสมอ

    foreign_keys ต้องเปิดทุกครั้ง มิฉะนั้น ON DELETE CASCADE ของ consents
    จะไม่ทำงาน และการถอนความยินยอมจะไม่ลบเวกเตอร์ใบหน้าตามไป
    """
    target = path or config.DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # ทนไฟดับได้ดีกว่าบนการ์ด/แฟลชไดรฟ์
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """สร้างตารางทั้งหมด (ปลอดภัยเมื่อเรียกซ้ำ)"""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """ทำหลายคำสั่งให้สำเร็จหรือล้มเหลวพร้อมกัน"""
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
