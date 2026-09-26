"""ทดสอบเส้นทางหลักของ API ทั้งหมดโดยยิงเข้าเซิร์ฟเวอร์ที่รันอยู่จริง

    .venv/Scripts/python.exe scripts/smoke.py [--base http://127.0.0.1:8000]

ครอบคลุมทั้งเส้นทางปกติและกฎด้านความเป็นส่วนตัวที่ห้ามพัง
คืนรหัส 0 เมื่อผ่านทั้งหมด
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

PASS, FAIL = "ผ่าน", "ไม่ผ่าน"
_results: list[tuple[bool, str, str]] = []


def call(base: str, method: str, path: str, *, token: str | None = None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Kiosk-Session", token)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((ok, name, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    base = parser.parse_args().base

    print("1. ข้อมูลตั้งต้นของตู้")
    status, boot = call(base, "GET", "/api/bootstrap")
    check(status == 200, "เรียก /api/bootstrap ได้", f"HTTP {status}")
    check(
        boot["department"]["name"] == "สาขาวิชาวิทยาการคอมพิวเตอร์",
        "ชื่อสาขาถูกต้อง",
        boot["department"]["name"],
    )
    check(len(boot["quickQuestions"]) >= 9, "มีคำถามยอดนิยมครบ",
          f"{len(boot['quickQuestions'])} ข้อ")
    check(len(boot["announcements"]) > 0, "มีประกาศจากข่าวจริงของสาขา",
          f"{len(boot['announcements'])} รายการ")
    check(boot["hasSyntheticSchedule"] is True,
          "ระบบรู้ตัวว่าตารางเรียนยังเป็นข้อมูลสมมติ")
    dept = boot["department"]
    check(dept["officeLocation"] is not None and "ชั้น 6" in dept["officeLocation"],
          "ที่ตั้งสำนักงานตรงกับเว็บไซต์จริง", str(dept["officeLocation"])[:40])
    check(dept["officePhone"] == "(+66) 053 873890-3",
          "เบอร์โทรตรงกับเว็บไซต์จริง", str(dept["officePhone"]))
    check(dept["officeHours"] is None,
          "เวลาทำการเป็นค่าว่าง (ไม่มีในข้อมูลจริง จึงไม่แต่งขึ้นมา)")
    check(boot["term"]["dataUpdatedLabel"] is not None, "มีวันที่อัปเดตข้อมูลล่าสุด",
          str(boot["term"]["dataUpdatedLabel"]))

    print("\n2. ข้อมูลส่วนบุคคลต้องปิดไว้ก่อนยืนยันตัวตน")
    status, _ = call(base, "GET", "/api/me/schedule")
    check(status == 401, "ขอตารางเรียนโดยไม่มีเซสชันถูกปฏิเสธ", f"HTTP {status}")
    status, _ = call(base, "GET", "/api/me/schedule", token="not-a-real-token")
    check(status == 401, "โทเค็นมั่วถูกปฏิเสธ", f"HTTP {status}")

    print("\n3. ยืนยันตัวตนด้วยใบหน้า")
    status, cand = call(base, "POST", "/api/sim/face/recognized", body={})
    check(status == 200, "กล้อง (จำลอง) จำใบหน้าได้", cand.get("name", ""))
    status, _ = call(base, "POST", "/api/session/face-confirm",
                     body={"candidateToken": "ของปลอม"})
    check(status == 410, "candidateToken ปลอมใช้ไม่ได้", f"HTTP {status}")

    status, sess = call(base, "POST", "/api/session/face-confirm",
                        body={"candidateToken": cand["candidateToken"]})
    check(status == 200, "กด 'ใช่' แล้วเข้าสู่ระบบได้", sess["student"]["name"])
    token = sess["token"]

    status, _ = call(base, "POST", "/api/session/face-confirm",
                     body={"candidateToken": cand["candidateToken"]})
    check(status == 410, "candidateToken ใช้ซ้ำไม่ได้", f"HTTP {status}")

    print("\n4. ความเป็นส่วนตัวของข้อมูลที่ส่งออกหน้าจอ")
    student = sess["student"]
    check("••••" in student["studentIdMasked"], "รหัสนักศึกษาถูกปิดบัง",
          student["studentIdMasked"])
    check(
        "6604101001" not in json.dumps(sess, ensure_ascii=False),
        "ไม่มีรหัสนักศึกษาเต็มหลุดออกมาใน response",
    )

    print("\n5. ตารางเรียนและกำหนดสอบ")
    status, sched = call(base, "GET", "/api/me/schedule", token=token)
    check(status == 200 and sched["hasSchedule"], "ดึงตารางเรียนได้")
    nxt = sched["nextClass"]
    check(nxt is not None, "คำนวณคาบถัดไปได้",
          f"{nxt['item']['code']} {nxt['item']['name']} · {nxt['dayLabel']} {nxt['item']['start']}")
    check(nxt["countdown"].startswith("อีก") or nxt["ongoing"],
          "มีข้อความนับถอยหลัง", nxt["countdown"])
    check(len(sched["week"]) == 5, "ตารางทั้งสัปดาห์มีจันทร์–ศุกร์ครบ")

    status, exams = call(base, "GET", "/api/me/exams", token=token)
    check(status == 200 and len(exams["exams"]) == 3, "กำหนดสอบมาจากวิชาที่ลงทะเบียน",
          f"{len(exams['exams'])} วิชา")

    print("\n6. ผู้ช่วยตอบคำถาม — คำตอบทุกข้อต้องมีแหล่งที่มา")
    for qid, expect in [
        ("next-class", "db"),
        ("room-floor", "db"),
        ("exam-subject", "db"),
        ("office-contact", "db"),
        ("scholarship-detail", "none"),
    ]:
        status, res = call(base, "POST", "/api/assistant/ask", token=token,
                           body={"questionId": qid, "channel": "แตะ"})
        ans = res["answer"]
        check(status == 200 and ans["source"] == expect,
              f"คำถาม '{ans.get('label') or qid}' → แหล่ง {ans['source']}",
              ans["title"])

    status, res = call(base, "POST", "/api/assistant/ask", token=token,
                       body={"questionId": "contact-teacher"})
    ans = res["answer"]
    check(ans["source"] == "db" and any("@mju.ac.th" in l for l in ans["lines"]),
          "ตอบผู้สอนด้วยอีเมลจริงของบุคลากร", ans["title"])

    status, res = call(base, "POST", "/api/assistant/ask", token=token,
                       body={"questionId": "room-floor"})
    ans = res["answer"]
    check(not any("None" in l for l in ans["lines"]),
          "คำตอบเรื่องห้องไม่มีค่าว่างหลุดออกมา", " / ".join(ans["lines"])[:70])

    status, res = call(base, "POST", "/api/assistant/ask", token=token,
                       body={"questionId": "add-drop", "online": False})
    check(res["answer"].get("offlineBlocked") is True,
          "คำถาม AI ถูกปิดตอนออฟไลน์", res["answer"]["title"])

    status, res = call(base, "POST", "/api/assistant/ask", token=token,
                       body={"questionId": "next-class", "online": False})
    check(res["answer"]["source"] == "db",
          "คำถามจากฐานข้อมูลยังตอบได้ตอนออฟไลน์", res["answer"]["title"])

    print("\n7. โหมดกรอกรหัสนักศึกษา (ไม่มีการยืนยันตัวตน)")
    status, kp = call(base, "POST", "/api/session/student-id",
                      body={"studentId": "6604101388"})
    check(status == 200 and kp["restricted"] is True,
          "เข้าสู่ระบบด้วยรหัสได้ แต่ถูกทำเครื่องหมายว่าไม่ยืนยันตัวตน")
    check(kp["student"]["advisor"] is None,
          "โหมดนี้ไม่เปิดเผยชื่ออาจารย์ที่ปรึกษา")
    kp_token = kp["token"]

    status, _ = call(base, "GET", "/api/me/schedule", token=kp_token)
    check(status == 200, "ยังดูตารางเรียนได้")
    status, _ = call(base, "DELETE", "/api/me/face", token=kp_token)
    check(status == 403, "แต่ลบข้อมูลใบหน้าของคนอื่นไม่ได้", f"HTTP {status}")

    status, _ = call(base, "POST", "/api/session/student-id",
                     body={"studentId": "0000000000"})
    check(status == 404, "รหัสที่ไม่มีในระบบถูกปฏิเสธ", f"HTTP {status}")

    print("\n8. ออกจากระบบแล้วข้อมูลต้องหายทันที")
    call(base, "DELETE", "/api/session", token=token)
    status, _ = call(base, "GET", "/api/me/schedule", token=token)
    check(status == 401, "โทเค็นเดิมใช้ไม่ได้อีก", f"HTTP {status}")

    failed = [name for ok, name, _ in _results if not ok]
    print(f"\n{'=' * 52}")
    print(f"ผ่าน {len(_results) - len(failed)}/{len(_results)} ข้อ")
    for name in failed:
        print(f"  ไม่ผ่าน: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
