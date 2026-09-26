"""ปรับโครงฐานข้อมูลของตู้ที่ติดตั้งไปแล้ว

schema.sql ใช้ CREATE TABLE IF NOT EXISTS จึงสร้างตารางใหม่ได้อย่างเดียว
แก้ตารางที่มีอยู่แล้วไม่ได้ ไฟล์นี้จึงรับหน้าที่นั้น

ทุกขั้นตอนต้องเรียกซ้ำได้โดยไม่เกิดผลข้างเคียง (idempotent)
เพราะถูกเรียกทุกครั้งที่เซิร์ฟเวอร์เริ่มทำงาน

เหตุผลที่ไม่ใช้วิธี "ลบฐานข้อมูลแล้วสร้างใหม่": ตู้ที่ให้บริการแล้วมีเวกเตอร์ใบหน้า
และบันทึกความยินยอมอยู่ ซึ่งลบทิ้งไม่ได้เพราะผู้ใช้ต้องมาลงทะเบียนใหม่ทั้งหมด
"""

from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger("kiosk.db")


def _table_sql(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row["sql"] if row else ""


def _add_typed_channel(conn: sqlite3.Connection) -> bool:
    """เพิ่มช่องทาง 'พิมพ์' ให้สถิติการใช้งาน

    เดิมรองรับแค่ 'เสียง' กับ 'แตะ' แต่หน้าต่างแชทมีช่องพิมพ์ข้อความด้วย
    SQLite แก้ CHECK constraint ตรง ๆ ไม่ได้ ต้องสร้างตารางใหม่แล้วย้ายข้อมูล
    """
    current = _table_sql(conn, "usage_events")
    if not current or "พิมพ์" in current:
        return False

    conn.executescript(
        """
        PRAGMA foreign_keys = OFF;

        CREATE TABLE usage_events_new (
          id             INTEGER PRIMARY KEY AUTOINCREMENT,
          occurred_at    TEXT NOT NULL,
          question_kind  TEXT,
          channel        TEXT    CHECK (channel IN ('เสียง', 'แตะ', 'พิมพ์')),
          answer_source  TEXT    CHECK (answer_source IN ('ฐานข้อมูล', 'AI', 'ไม่พบ')),
          latency_ms     INTEGER
        );

        INSERT INTO usage_events_new (id, occurred_at, question_kind, answer_source, channel, latency_ms)
          SELECT id, occurred_at, question_kind, answer_source, channel, latency_ms FROM usage_events;

        DROP TABLE usage_events;
        ALTER TABLE usage_events_new RENAME TO usage_events;
        CREATE INDEX IF NOT EXISTS ix_usage_time ON usage_events (occurred_at);

        PRAGMA foreign_keys = ON;
        """
    )
    return True


STEPS = (
    ("เพิ่มช่องทาง 'พิมพ์' ในสถิติการใช้งาน", _add_typed_channel),
)


def run(conn: sqlite3.Connection) -> None:
    for label, step in STEPS:
        try:
            if step(conn):
                conn.commit()
                log.info("ปรับฐานข้อมูล: %s", label)
        except sqlite3.Error:
            conn.rollback()
            log.exception("ปรับฐานข้อมูลไม่สำเร็จ: %s", label)
            raise
