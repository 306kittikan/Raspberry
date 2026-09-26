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


def _add_student_status(conn: sqlite3.Connection) -> bool:
    """เพิ่มคำนำหน้าชื่อและสถานภาพนักศึกษาจากระบบทะเบียน

    ก่อนหน้านี้เก็บแค่ชื่อกับชั้นปี ไม่มีทางรู้ว่าใครลาออกหรือพ้นสภาพไปแล้ว
    ตู้จึงยังแสดงตารางเรียนให้คนที่ไม่ได้เป็นนักศึกษาแล้วได้ ซึ่งไม่ควรเกิดขึ้น
    """
    have = {r["name"] for r in conn.execute("PRAGMA table_info(students)")}
    missing = [
        ("prefix", "TEXT"),
        ("entry_year", "INTEGER"),
        ("program_code", "TEXT"),
        ("status_code", "TEXT"),
        ("status_label", "TEXT"),
        ("updated_at", "TEXT"),
    ]
    added = False
    for column, kind in missing:
        if column not in have:
            conn.execute(f"ALTER TABLE students ADD COLUMN {column} {kind}")
            added = True

    if "active" not in have:
        # ค่าตั้งต้นเป็น 1 เพราะข้อมูลเดิมยังไม่รู้สถานภาพ ถือว่ายังศึกษาอยู่ไว้ก่อน
        conn.execute(
            "ALTER TABLE students ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
        )
        added = True

    # สร้างเสมอ ไม่ใช่เฉพาะตอนเพิ่มคอลัมน์ เพราะฐานข้อมูลที่สร้างใหม่จาก schema.sql
    # ก็ยังไม่มี index นี้ (schema.sql สร้างไม่ได้ ดูคำอธิบายในไฟล์นั้น)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_students_active ON students (active)")
    return added


STEPS = (
    ("เพิ่มช่องทาง 'พิมพ์' ในสถิติการใช้งาน", _add_typed_channel),
    ("เพิ่มคำนำหน้าชื่อและสถานภาพนักศึกษา", _add_student_status),
)


def run(conn: sqlite3.Connection) -> None:
    for label, step in STEPS:
        try:
            changed = step(conn)
            # commit ทุกครั้ง เพราะบางขั้นตอนสร้าง index โดยไม่ได้เพิ่มคอลัมน์
            # ซึ่งถือว่า "ไม่มีอะไรเปลี่ยน" แต่ยังต้องบันทึกลงดิสก์
            conn.commit()
            if changed:
                log.info("ปรับฐานข้อมูล: %s", label)
        except sqlite3.Error:
            conn.rollback()
            log.exception("ปรับฐานข้อมูลไม่สำเร็จ: %s", label)
            raise
