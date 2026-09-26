"""ค่าตั้งต้นของระบบ อ่านจากตัวแปรสภาพแวดล้อมได้ทั้งหมด"""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SERVER_DIR.parent

load_dotenv(SERVER_DIR / ".env")


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ---- ฐานข้อมูล ----
DB_PATH = Path(os.getenv("KIOSK_DB", SERVER_DIR / "data" / "kiosk.db"))

# ---- เขตเวลา ----
# ตู้ติดตั้งในประเทศไทย ใช้เวลาไทยเสมอ ไม่อิงนาฬิกาของเครื่องที่พัฒนา
TZ = ZoneInfo(os.getenv("KIOSK_TZ", "Asia/Bangkok"))

# ---- ความเป็นส่วนตัว ----
# ฉบับของคำประกาศความยินยอม เปลี่ยนค่านี้เมื่อแก้ข้อความบนหน้าขอความยินยอม
# ความยินยอมฉบับเก่าจะยังอยู่ในฐานข้อมูลเพื่อเป็นหลักฐานว่าผู้ใช้ยินยอมกับข้อความใด
CONSENT_POLICY_VERSION = os.getenv("KIOSK_CONSENT_VERSION", "2569-1")

# โหมดกรอกรหัสนักศึกษาไม่มีการยืนยันตัวตน (ใครก็กรอกรหัสผู้อื่นได้)
# จึงจำกัดข้อมูลที่แสดง: ดูตารางเรียนได้ แต่ไม่เห็นข้อมูลติดต่อ/ที่ปรึกษา
# และห้ามเข้าหน้าจัดการข้อมูลใบหน้าเด็ดขาด
KEYPAD_MODE_RESTRICTED = _flag("KIOSK_KEYPAD_RESTRICTED", True)

# ---- อายุเซสชัน (วินาที) ----
# ตรงกับ TIMING ใน web/src/state/KioskProvider.jsx
SESSION_IDLE_SECONDS = int(os.getenv("KIOSK_SESSION_IDLE", "30"))
SESSION_GRACE_SECONDS = int(os.getenv("KIOSK_SESSION_GRACE", "15"))

# ---- โหมดจำลอง ----
# เปิดเส้นทาง /api/sim/* สำหรับพัฒนาและสาธิตโดยไม่ต้องมีกล้อง
# ต้องปิดเมื่อติดตั้งใช้งานจริง มิฉะนั้นสวมรอยเป็นนักศึกษาคนใดก็ได้
SIM_MODE = _flag("KIOSK_SIM", True)

# ---- รู้จำใบหน้า ----
FACE_MODEL_PACK = os.getenv("KIOSK_FACE_MODEL", "buffalo_s")
FACE_MODEL_DIR = Path(os.getenv("KIOSK_FACE_MODEL_DIR", SERVER_DIR / "models"))
# ระยะโคไซน์ขั้นต่ำที่ถือว่า "ใช่คนเดียวกัน" — ArcFace/buffalo แนะนำราว 0.35–0.45
# ตั้งสูงไว้ก่อนเพื่อลดโอกาส "จำผิดคน" ซึ่งเป็นความเสี่ยงที่ระบุไว้ในเอกสาร
FACE_MATCH_THRESHOLD = float(os.getenv("KIOSK_FACE_THRESHOLD", "0.45"))
# ช่องว่างขั้นต่ำระหว่างอันดับ 1 กับอันดับ 2 ถ้าใกล้กันเกินไปให้ถือว่าจำไม่ได้
FACE_MATCH_MARGIN = float(os.getenv("KIOSK_FACE_MARGIN", "0.05"))
CAMERA_SOURCE = os.getenv("KIOSK_CAMERA", "auto")  # auto | picamera | <index> | off

# ---- ผู้ช่วย AI ----
ANTHROPIC_MODEL = os.getenv("KIOSK_AI_MODEL", "claude-opus-5")
AI_ENABLED = _flag("KIOSK_AI_ENABLED", True) and bool(
    os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
)
AI_TIMEOUT_SECONDS = float(os.getenv("KIOSK_AI_TIMEOUT", "20"))

# ---- CORS (เฉพาะตอนพัฒนา ตอนใช้งานจริงเสิร์ฟจาก origin เดียวกัน) ----
DEV_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "KIOSK_DEV_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]
