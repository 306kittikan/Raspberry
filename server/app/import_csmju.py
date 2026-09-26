"""นำเข้าข้อมูลจริงของสาขาจาก csmju_dataset/

    python -m app.import_csmju [--dataset ../csmju_dataset]

ชุดข้อมูลเก็บจากเว็บไซต์ https://gates.csmju.com เมื่อ 26 กันยายน 2569
ดึงข้อมูลใหม่ได้โดยเรียก API ต้นทางตามที่อธิบายไว้ใน csmju_dataset/README.md

สิ่งที่นำเข้า
  - ข้อมูลสาขาและช่องทางติดต่อ        (แทนข้อมูลที่เคยสมมติไว้ ซึ่งผิดจากของจริง)
  - อาคาร 3 แห่ง และห้องเรียน 9 ห้อง
  - บุคลากร 15 คน (ตู้แสดงเฉพาะคนที่เปิดเผยข้อมูลไว้)
  - รายวิชา 253 วิชา
  - ข่าว/กิจกรรมที่เผยแพร่แล้ว → ประกาศบนหน้าจอพัก
  - 352 ชิ้นเอกสารสำหรับผู้ช่วย AI

สิ่งที่ชุดข้อมูลนี้ "ไม่มี" และยังต้องขอจากสาขา
  - ตารางเรียนรายสัปดาห์ (วัน เวลา ห้อง อาจารย์ผู้สอน)
  - กำหนดสอบ
  - เวลาทำการของสำนักงาน
  ทั้งสามอย่างถูกปล่อยว่างไว้โดยตั้งใจ ระบบจะตอบว่า "ไม่พบข้อมูล" แทนการเดา
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from . import config, db as db_module, thai

DEFAULT_DATASET = config.ROOT_DIR / "csmju_dataset"

# ชื่อเอกสารอ้างอิงที่จะแสดงบนจอ แยกตามชนิดของชิ้นเอกสาร
# ผู้ใช้ต้องอ่านแล้วรู้ทันทีว่าคำตอบมาจากไหน
DOC_LABELS: dict[str, str] = {
    "organization": "เว็บไซต์สาขาวิชาฯ · ภาพรวมสาขา",
    "contact": "เว็บไซต์สาขาวิชาฯ · ช่องทางติดต่อ",
    "facilities": "เว็บไซต์สาขาวิชาฯ · อาคารและห้องเรียน",
    "features": "เว็บไซต์สาขาวิชาฯ · จุดเด่นหลักสูตร",
    "about": "เว็บไซต์สาขาวิชาฯ · เกี่ยวกับสาขา",
    "program": "เว็บไซต์สาขาวิชาฯ · รายละเอียดหลักสูตร",
    "program_objectives": "เว็บไซต์สาขาวิชาฯ · วัตถุประสงค์ของหลักสูตร",
    "program_plo": "เว็บไซต์สาขาวิชาฯ · ผลการเรียนรู้ที่คาดหวัง",
    "program_structure": "เว็บไซต์สาขาวิชาฯ · โครงสร้างหลักสูตร",
    "study_plan": "เว็บไซต์สาขาวิชาฯ · แผนการศึกษา",
    "course": "เว็บไซต์สาขาวิชาฯ · ข้อมูลรายวิชา",
    "personnel": "เว็บไซต์สาขาวิชาฯ · ทำเนียบบุคลากร",
    "news": "เว็บไซต์สาขาวิชาฯ · ข่าวและกิจกรรม",
    "project": "เว็บไซต์สาขาวิชาฯ · โครงงานนักศึกษา",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    # ไฟล์บันทึกเป็น UTF-8 with BOM เพื่อให้เปิดใน Excel แล้วภาษาไทยไม่เพี้ยน
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def flag(value: str | None) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def clean(value: str | None) -> str | None:
    """ช่องว่างใน CSV หมายถึง 'ไม่มีข้อมูล' ไม่ใช่สตริงว่าง"""
    if value is None:
        return None
    text = value.strip()
    return text or None


def short_room_name(name: str) -> str | None:
    """'ห้องปฏิบัติการคอมพิวเตอร์ 3 (Lab 3)' → 'Lab 3' สำหรับแสดงตัวใหญ่บนจอ"""
    match = re.search(r"\(([^)]+)\)\s*$", name)
    return match.group(1).strip() if match else None


# ------------------------------------------------------------
def import_department(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    org = data["organization"]
    contacts = {c["type"]: c for c in org.get("contacts", [])}

    conn.execute(
        """INSERT OR REPLACE INTO department
           (id, name, faculty, abbr, website, office_location, office_hours,
            office_phone, office_email)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "สาขาวิชาวิทยาการคอมพิวเตอร์",
            "คณะวิทยาศาสตร์ มหาวิทยาลัยแม่โจ้",
            org.get("short_name", "CSMJU"),
            org.get("website"),
            clean(contacts.get("address", {}).get("value")),
            # เวลาทำการไม่มีในเว็บไซต์ของสาขา จึงปล่อยว่างไว้ ห้ามแต่งขึ้นมาเอง
            None,
            clean(contacts.get("phone", {}).get("value")),
            clean(contacts.get("email", {}).get("value")),
        ),
    )

    conn.execute("DELETE FROM contacts")
    for c in org.get("contacts", []):
        conn.execute(
            """INSERT INTO contacts (source_id, type, title, description, value, label, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (c.get("contact_id"), c["type"], c["title"], clean(c.get("description")),
             c["value"], clean(c.get("label")), c.get("sort_order") or 0),
        )


def import_places(conn: sqlite3.Connection, ds: Path) -> None:
    for b in read_csv(ds / "csv" / "buildings.csv"):
        conn.execute(
            """INSERT INTO buildings (source_id, name) VALUES (?, ?)
               ON CONFLICT(source_id) DO UPDATE SET name = excluded.name""",
            (b["building_id"], b["name"]),
        )

    for r in read_csv(ds / "csv" / "rooms.csv"):
        building = conn.execute(
            "SELECT id FROM buildings WHERE source_id = ?", (r["building_id"],)
        ).fetchone()
        name = r["name_th"]
        conn.execute(
            """INSERT INTO rooms
                   (source_id, code, name, short_name, room_type, building_id, floor, capacity)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_id) DO UPDATE SET
                   code = excluded.code, name = excluded.name,
                   short_name = excluded.short_name, room_type = excluded.room_type,
                   building_id = excluded.building_id, floor = excluded.floor,
                   capacity = excluded.capacity""",
            (r["room_id"], r["room_code"], name, short_room_name(name),
             clean(r["room_type"]), building["id"] if building else None,
             int(r["floor"]) if r["floor"] else None,
             int(r["capacity"]) if r["capacity"] else None),
        )


def import_personnel(conn: sqlite3.Connection, ds: Path) -> int:
    rows = read_csv(ds / "csv" / "personnel.csv")
    for p in rows:
        conn.execute(
            """INSERT INTO personnel
                   (source_id, prefix, fullname_th, fullname_en, academic_position,
                    administrative_position, personnel_type, education, email, phone,
                    expertise, work_status, is_public)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_id) DO UPDATE SET
                   prefix = excluded.prefix, fullname_th = excluded.fullname_th,
                   academic_position = excluded.academic_position,
                   administrative_position = excluded.administrative_position,
                   email = excluded.email, phone = excluded.phone,
                   expertise = excluded.expertise, is_public = excluded.is_public""",
            (p["personnel_id"], clean(p["prefix"]), p["fullname_th"], clean(p["fullname_en"]),
             clean(p["academic_position"]), clean(p["administrative_position"]),
             clean(p["personnel_type"]), clean(p["education"]), clean(p["email"]),
             clean(p["phone"]), clean(p["expertise"]), clean(p["work_status"]),
             1 if flag(p["profile_is_public"]) else 0),
        )
    return sum(1 for p in rows if flag(p["profile_is_public"]))


def import_courses(conn: sqlite3.Connection, ds: Path) -> None:
    for c in read_csv(ds / "csv" / "courses.csv"):
        conn.execute(
            """INSERT INTO courses
                   (source_id, code, name, name_en, credits, credit_format, description)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(code) DO UPDATE SET
                   source_id = excluded.source_id, name = excluded.name,
                   name_en = excluded.name_en, credits = excluded.credits,
                   credit_format = excluded.credit_format,
                   description = excluded.description""",
            (c["course_id"], c["course_code"], c["title_th"], clean(c["title_en"]),
             int(c["credits"]) if c["credits"] else None,
             clean(c["credit_format"]), clean(c["description"])),
        )


def import_announcements(conn: sqlite3.Connection, ds: Path) -> int:
    """ข่าว/กิจกรรมที่เผยแพร่แล้ว → ประกาศวนแสดงบนหน้าจอพัก

    ตาราง announcements ของต้นทางมี 2 รายการแต่เป็นสถานะ draft ทั้งคู่
    จึงใช้ articles เป็นแหล่งประกาศแทน
    """
    conn.execute("DELETE FROM announcements")
    rows = [a for a in read_csv(ds / "csv" / "articles.csv") if flag(a["published"])]
    rows.sort(key=lambda a: a["published_date"], reverse=True)

    for order, a in enumerate(rows):
        # เนื้อหาข่าวยาวเกินกว่าจะอ่านจบจากระยะยืน ตัดเหลือประโยคแรก
        body = re.sub(r"\s+", " ", a["content"]).strip()
        detail = body[:150].rstrip() + ("…" if len(body) > 150 else "")
        conn.execute(
            """INSERT INTO announcements (tag, title, detail, starts_on, sort_order)
               VALUES (?, ?, ?, ?, ?)""",
            (clean(a["category"]) or "ข่าวสาขา", a["title"].strip(), detail,
             clean(a["published_date"]), order),
        )
    return len(rows)


def import_knowledge(conn: sqlite3.Connection, ds: Path, crawled_at: str | None) -> tuple[int, int]:
    """นำเข้าชิ้นเอกสารสำหรับผู้ช่วย AI

    จัดกลุ่มเป็นเอกสารตามชนิดของชิ้นเอกสาร เพราะข้อความอ้างอิงที่แสดงบนจอ
    ต้องอ่านแล้วเข้าใจได้ทันทีว่ามาจากส่วนไหนของเว็บไซต์
    """
    chunks = read_jsonl(ds / "rag" / "csmju_knowledge_chunks.jsonl")
    now = thai.now().isoformat(timespec="seconds")
    effective = (crawled_at or "")[:10] or None

    conn.execute("DELETE FROM documents")  # doc_chunks ถูกลบตาม ON DELETE CASCADE

    doc_ids: dict[str, int] = {}
    counters: dict[str, int] = {}

    for chunk in chunks:
        kind = chunk["type"]
        if kind not in doc_ids:
            label = DOC_LABELS.get(kind, f"เว็บไซต์สาขาวิชาฯ · {kind}")
            cur = conn.execute(
                """INSERT INTO documents (title, citation_label, source_path, effective_date, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (label, label, "https://gates.csmju.com", effective, now),
            )
            doc_ids[kind] = cur.lastrowid
            counters[kind] = 0

        conn.execute(
            """INSERT INTO doc_chunks (document_id, ordinal, page, content, source_url, source_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (doc_ids[kind], counters[kind], chunk.get("title"), chunk["text"],
             chunk.get("source_url"), chunk.get("id")),
        )
        counters[kind] += 1

    return len(doc_ids), len(chunks)


# ------------------------------------------------------------
def import_all(conn: sqlite3.Connection, ds: Path) -> dict[str, Any]:
    if not ds.is_dir():
        raise FileNotFoundError(f"ไม่พบชุดข้อมูลที่ {ds}")

    data = json.loads((ds / "csmju_dataset.json").read_text(encoding="utf-8"))
    crawled_at = data.get("meta", {}).get("crawled_at")

    with db_module.transaction(conn):
        import_department(conn, data)
        import_places(conn, ds)
        public_staff = import_personnel(conn, ds)
        import_courses(conn, ds)
        news = import_announcements(conn, ds)
        docs, chunks = import_knowledge(conn, ds, crawled_at)

    return {
        "crawled_at": crawled_at,
        "buildings": conn.execute("SELECT COUNT(*) c FROM buildings").fetchone()["c"],
        "rooms": conn.execute("SELECT COUNT(*) c FROM rooms").fetchone()["c"],
        "personnel": conn.execute("SELECT COUNT(*) c FROM personnel").fetchone()["c"],
        "personnel_public": public_staff,
        "courses": conn.execute("SELECT COUNT(*) c FROM courses").fetchone()["c"],
        "contacts": conn.execute("SELECT COUNT(*) c FROM contacts").fetchone()["c"],
        "announcements": news,
        "documents": docs,
        "doc_chunks": chunks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="นำเข้าข้อมูลจริงของสาขาจาก csmju_dataset")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args(argv)

    conn = db_module.connect()
    db_module.init_db(conn)
    stats = import_all(conn, args.dataset)
    conn.close()

    print(f"นำเข้าข้อมูลจริงจาก {args.dataset} เรียบร้อย")
    print(f"  เก็บข้อมูลเมื่อ  {stats['crawled_at']}")
    for key in ("buildings", "rooms", "personnel", "courses", "contacts",
                "announcements", "documents", "doc_chunks"):
        print(f"  {key:16s} {stats[key]:5d}")
    print(f"  (บุคลากรที่เปิดเผยข้อมูลสาธารณะ {stats['personnel_public']} คน)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
