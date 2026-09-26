"""จัดรูปแบบวันที่/เวลาแบบไทย และคำนวณคาบเรียนถัดไป

ฝั่งเซิร์ฟเวอร์เป็นผู้คำนวณ "คาบถัดไป" และ "นับถอยหลัง" ทั้งหมด
เพื่อให้คำตอบที่มาจากฐานข้อมูลเป็นชุดเดียวกันไม่ว่าจะถามผ่านหน้าจอหรือผ่านผู้ช่วย
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from . import config

THAI_MONTHS = (
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
)

# index = ISO weekday - 1 (1 = จันทร์ ... 7 = อาทิตย์)
THAI_WEEKDAYS = ("จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์")


def now() -> datetime:
    """เวลาปัจจุบันตามเขตเวลาของตู้ (ไม่ใช่ของเครื่องที่พัฒนา)"""
    return datetime.now(config.TZ)


def buddhist_year(d: date) -> int:
    return d.year + 543


def weekday_name(d: date) -> str:
    return THAI_WEEKDAYS[d.isoweekday() - 1]


def format_date(d: date) -> str:
    """'26 กันยายน 2569'"""
    return f"{d.day} {THAI_MONTHS[d.month - 1]} {buddhist_year(d)}"


def format_full_date(d: date) -> str:
    """'วันเสาร์ที่ 26 กันยายน 2569'"""
    return f"วัน{weekday_name(d)}ที่ {format_date(d)}"


def format_datetime(dt: datetime) -> str:
    """'22 กันยายน 2569 เวลา 06.00 น.'"""
    return f"{format_date(dt.date())} เวลา {dt.hour:02d}.{dt.minute:02d} น."


def parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def at_time(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, parse_hhmm(hhmm), tzinfo=config.TZ)


def format_countdown(delta: timedelta) -> str:
    """'อีก 1 ชั่วโมง 20 นาที' — ข้อความเดียวกับที่ UI เคยคำนวณเอง"""
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "ถึงเวลาเรียนแล้ว"

    total_minutes = total_seconds // 60
    if total_minutes < 1:
        return f"อีก {max(1, total_seconds)} วินาที"

    hours, minutes = divmod(total_minutes, 60)
    if hours >= 24:
        days, rest_hours = divmod(hours, 24)
        return f"อีก {days} วัน" if rest_hours == 0 else f"อีก {days} วัน {rest_hours} ชั่วโมง"
    if hours == 0:
        return f"อีก {minutes} นาที"
    if minutes == 0:
        return f"อีก {hours} ชั่วโมง"
    return f"อีก {hours} ชั่วโมง {minutes} นาที"


def relative_day_label(day_offset: int, d: date) -> str:
    """'วันนี้' / 'พรุ่งนี้' / 'วันจันทร์'"""
    if day_offset == 0:
        return "วันนี้"
    if day_offset == 1:
        return "พรุ่งนี้"
    return f"วัน{weekday_name(d)}"
