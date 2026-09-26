"""อ่านรายชื่อนักศึกษาจากไฟล์รายงานของระบบทะเบียนมหาวิทยาลัย

ระบบทะเบียนส่งออกเป็น RTF (นามสกุล .asp แต่เนื้อในเป็น RTF)
เข้ารหัสภาษาไทยด้วย cp874 และจัดเป็นตาราง 4 คอลัมน์

    เลขที่ | รหัสประจำตัว | ชื่อ | สถานภาพ
    1      | 6604101336   | นางสาวธัญพิมล วังใน | 10

หัวรายงานบอกหลักสูตร คณะ และปีการศึกษาที่เข้า ซึ่งใช้คำนวณชั้นปีได้

เขียนตัวอ่านเองแทนการใช้ไลบรารีภายนอก เพราะ
  1. ต้องลงเพิ่มบน Raspberry Pi ซึ่งมีพื้นที่และแรงจำกัด
  2. รูปแบบไฟล์จากระบบทะเบียนคงที่ ไม่ต้องรองรับ RTF ทุกความสามารถ
  3. โค้ดที่อ่านเองตรวจสอบได้ว่าไม่ได้ส่งข้อมูลนักศึกษาออกไปไหน
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# กลุ่ม RTF ที่เป็นข้อมูลภายในของโปรแกรม ไม่ใช่เนื้อหา
_META_GROUPS = ("fonttbl", "colortbl", "stylesheet", "info", "listtable", "listoverridetable")

_ROW = re.compile(r"^\s*(\d+)\s*\t\s*(\d{8,12})\s*\t\s*(.+?)\s*\t\s*(\S*)\s*$")
_PROGRAM = re.compile(r"หลักสูตร\s*(\d+)\s*:\s*(.+?)\s*(?:\t|$)")
_ENTRY_YEAR = re.compile(r"ปีการศึกษาที่เข้า\s*(\d{4})")
_FACULTY = re.compile(r"คณะ\s+(\S+)")
_STATUS_DEF = re.compile(r"(\d{2})\s*:\s*([^,]+)")

PREFIXES = ("นางสาว", "นาง", "นาย", "ว่าที่ร้อยตรี", "ว่าที่ร้อยตรีหญิง")

# สถานภาพที่ถือว่ายังเป็นนักศึกษาและใช้ตู้ได้
# 10 กำลังศึกษา · 11 รักษาสภาพ · 12/13 ลาพัก · 15 ชำระเงินไม่ครบ
# ที่เหลือ (ลาออก พ้นสภาพ สำเร็จการศึกษา) ไม่ควรเห็นตารางเรียนของภาคปัจจุบัน
ACTIVE_STATUS = {"10", "11", "12", "13", "15", "17", "18", "19"}


@dataclass(slots=True)
class RosterStudent:
    student_id: str
    prefix: str | None
    name: str
    status_code: str
    status_label: str | None
    active: bool


@dataclass(slots=True)
class Roster:
    program_code: str | None = None
    program_name: str | None = None
    faculty: str | None = None
    entry_year: int | None = None
    students: list[RosterStudent] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def active_count(self) -> int:
        return sum(1 for s in self.students if s.active)


def _unescape(chunk: str) -> str:
    """แปลง \\'xx กลับเป็นไบต์ แล้วถอดรหัสด้วย cp874 (ภาษาไทย)"""
    out = bytearray()
    i = 0
    n = len(chunk)
    while i < n:
        ch = chunk[i]
        if ch == "\\" and i + 1 < n:
            nxt = chunk[i + 1]
            if nxt == "'" and i + 3 < n:
                try:
                    out.append(int(chunk[i + 2 : i + 4], 16))
                    i += 4
                    continue
                except ValueError:
                    pass
            if nxt in "\\{}":
                out.append(ord(nxt))
                i += 2
                continue
        out.append(ord(ch) & 0xFF)
        i += 1
    return out.decode("cp874", errors="replace")


def rtf_to_lines(data: bytes) -> list[str]:
    """แปลงไฟล์ RTF เป็นบรรทัดข้อความ โดยใช้ \\t คั่นช่องตาราง"""
    text = data.decode("latin-1")

    for name in _META_GROUPS:
        text = re.sub(r"\{\\" + name + r"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", text)
    text = re.sub(r"\{\\\*[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", text)

    text = re.sub(r"\\(?:par|line|row)\b", "\n", text)
    text = re.sub(r"\\cell\b", "\t", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d*[ ]?", "", text)
    text = text.replace("{", "").replace("}", "")

    content = _unescape(text)
    return [ln.strip() for ln in content.splitlines() if ln.strip(" \t")]


def split_name(full: str) -> tuple[str | None, str]:
    """แยกคำนำหน้าออกจากชื่อ

    ตู้ทักทายด้วยชื่อ การเก็บ "นางสาวธัญพิมล วังใน" ไว้ทั้งก้อน
    จะทำให้ขึ้นว่า "สวัสดี นางสาวธัญพิมล" ซึ่งอ่านแล้วแข็ง
    """
    cleaned = " ".join(full.split())
    for prefix in PREFIXES:
        if cleaned.startswith(prefix):
            return prefix, cleaned[len(prefix) :].strip()
    return None, cleaned


def parse(path: Path) -> Roster:
    lines = rtf_to_lines(path.read_bytes())
    roster = Roster()
    status_labels: dict[str, str] = {}

    for line in lines:
        flat = line.replace("\t", " ")

        if roster.program_code is None and (m := _PROGRAM.search(line)):
            roster.program_code = m.group(1)
            roster.program_name = m.group(2).strip()
        if roster.entry_year is None and (m := _ENTRY_YEAR.search(flat)):
            roster.entry_year = int(m.group(1))
        if roster.faculty is None and (m := _FACULTY.search(flat)):
            roster.faculty = m.group(1)

        # บรรทัดคำอธิบายรหัสสถานภาพ มีหลายคู่คั่นด้วยจุลภาค
        if flat.count(" : ") > 3:
            for code, label in _STATUS_DEF.findall(flat):
                status_labels.setdefault(code, label.strip())

        if not (m := _ROW.match(line)):
            continue

        student_id, raw_name, status = m.group(2), m.group(3), m.group(4)
        prefix, name = split_name(raw_name)

        if not name or name == "-":
            roster.skipped.append(f"{student_id}: ไม่มีชื่อในไฟล์ต้นทาง")
            continue

        roster.students.append(
            RosterStudent(
                student_id=student_id,
                prefix=prefix,
                name=name,
                status_code=status,
                status_label=None,
                active=status in ACTIVE_STATUS,
            )
        )

    for student in roster.students:
        student.status_label = status_labels.get(student.status_code)

    return roster


def study_year(entry_year: int | None, current_term_code: str | None) -> int | None:
    """คำนวณชั้นปีจากปีที่เข้ากับภาคการศึกษาปัจจุบัน

    รหัสภาค '2569-1' หมายถึงปีการศึกษา 2569 ภาคที่ 1
    เข้าปี 2566 ในปีการศึกษา 2569 จึงอยู่ชั้นปีที่ 4
    """
    if entry_year is None or not current_term_code:
        return None
    try:
        current_year = int(current_term_code.split("-")[0])
    except (ValueError, IndexError):
        return None
    year = current_year - entry_year + 1
    return year if 1 <= year <= 8 else None
