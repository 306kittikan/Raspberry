"""ตรวจว่าข้อความที่ตู้ตอบถูกแปลงเป็นคำอ่านได้ถูกต้อง

ตัวแยกเสียงภาษาไทยทิ้งอักษรอังกฤษกับตัวเลขที่ปนอยู่ในประโยค
คำตอบของตู้เต็มไปด้วยรหัสวิชา เวลา และชื่อห้อง
ถ้าแปลงผิด ตู้จะพูดข้อมูลผิดทั้งที่ข้อความบนจอถูก ซึ่งแย่กว่าไม่พูดเลย
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import tts  # noqa: E402

# (ข้อความบนจอ, สิ่งที่ต้องได้ยิน, สิ่งที่ต้องไม่ได้ยิน)
CASES: list[tuple[str, list[str], list[str]]] = [
    ("คาบถัดไป 15:00 น. ห้อง Lab คอม3-4",
     ["สิบห้านาฬิกา", "แล็บ"], ["15", "Lab", "น. "]),
    ("เรียน 13:00-15:00",
     ["สิบสามนาฬิกา", "ถึง", "สิบห้านาฬิกา"], ["13", "15"]),
    ("09:30 น.", ["เก้านาฬิกาครึ่ง"], ["09", "30"]),
    ("10301222 โครงสร้างข้อมูล",
     ["รหัสวิชา", "หนึ่ง ศูนย์ สาม"], ["10301222"]),
    ("ห้อง 3203 ชั้น 6", ["สาม สอง ศูนย์ สาม", "หก"], ["3203"]),
    ("อีเมล panuwat_m@mju.ac.th",
     ["ตามที่แสดงบนหน้าจอ"], ["panuwat", "@", "mju"]),
    ("ดูที่ https://cs.mju.ac.th/news",
     ["ตามที่แสดงบนหน้าจอ"], ["https", "cs.mju"]),
    ("วิชา IoT และ AI", ["ไอโอที", "เอไอ"], ["IoT", "AI"]),
    ("13:00 · ห้องเรียน", ["สิบสามนาฬิกา"], ["·"]),
]


def main() -> int:
    failed = 0
    for text, must, must_not in CASES:
        got = tts.speakable(text)
        bad = [w for w in must if w not in got] + [w for w in must_not if w in got]
        mark = "ผ่าน" if not bad else "ตก "
        print(f"  [{mark}] {text}")
        print(f"          → {got}")
        if bad:
            failed += 1
            print(f"          ผิดตรง {bad}")

    total = len(CASES)
    print()
    print("=" * 52)
    print(f"ผ่าน {total - failed}/{total} ข้อ")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
