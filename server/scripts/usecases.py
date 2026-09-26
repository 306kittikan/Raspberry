"""ทดสอบกรณีการใช้งานทั้งหมดตามที่ระบุไว้ใน docs/usecases.md

    .venv/Scripts/python.exe scripts/usecases.py
    .venv/Scripts/python.exe scripts/usecases.py --only UC-03
    .venv/Scripts/python.exe scripts/usecases.py --list

ทำงานระดับ API จึงไม่ต้องมีคนอยู่หน้ากล้อง ใช้เส้นทางจำลองแทนเหตุการณ์จากอุปกรณ์
ต้องเปิดเซิร์ฟเวอร์ไว้ก่อน และเปิดโหมดจำลอง (KIOSK_SIM=1)

เมื่อพบปัญหา จะพิมพ์สิ่งที่คาดหวังกับสิ่งที่ได้จริง เพื่อให้ไล่หาสาเหตุได้ทันที
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000"

_results: list[tuple[str, bool, str, str]] = []
_current = ""


# ------------------------------------------------------------
def call(method: str, path: str, *, token: str | None = None, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("X-Kiosk-Session", token)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else {})
    except urllib.error.URLError as exc:
        return 0, {"detail": f"ติดต่อเซิร์ฟเวอร์ไม่ได้: {exc.reason}"}


def check(ok: bool, name: str, expected: str = "", actual: str = "") -> bool:
    _results.append((_current, ok, name, "" if ok else f"ควรได้ {expected} · ได้จริง {actual}"))
    mark = "ผ่าน" if ok else "ไม่ผ่าน"
    print(f"    [{mark}] {name}")
    if not ok:
        print(f"           ควรได้  : {expected}")
        print(f"           ได้จริง : {actual}")
    return ok


def case(code: str, title: str) -> None:
    global _current
    _current = code
    print(f"\n{code}  {title}")


def login_student(student_id: str) -> tuple[int, dict]:
    return call("POST", "/api/session/student-id", body={"studentId": student_id})


def pick_students(n: int = 4) -> list[str]:
    """เลือกรหัสนักศึกษาที่ใช้ตู้ได้จากฐานข้อมูลจริง"""
    from app import db as db_module

    conn = db_module.connect()
    rows = conn.execute(
        "SELECT student_id FROM students WHERE active = 1 ORDER BY student_id LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [r["student_id"] for r in rows]


def pick_inactive() -> tuple[str, str] | None:
    from app import db as db_module

    conn = db_module.connect()
    row = conn.execute(
        "SELECT student_id, status_label FROM students WHERE active = 0 LIMIT 1"
    ).fetchone()
    conn.close()
    return (row["student_id"], row["status_label"] or "") if row else None


# ------------------------------------------------------------
def uc01_recognised_face() -> None:
    case("UC-01", "นักศึกษาที่ลงทะเบียนใบหน้าแล้ว ยืนหน้าตู้")

    students = pick_students(1)
    if not students:
        check(False, "มีนักศึกษาในระบบ", "อย่างน้อย 1 คน", "0 คน")
        return
    target = students[0]

    status, cand = call("POST", "/api/sim/face/recognized", body={"studentId": target})
    if not check(status == 200, "กล้องรายงานว่าจำใบหน้าได้", "HTTP 200", f"HTTP {status} {cand}"):
        return
    check("candidateToken" in cand and "name" in cand,
          "ได้โทเค็นและชื่อของผู้ที่ระบบคิดว่าใช่", "มี candidateToken + name", str(list(cand)))

    status, sess = call("POST", "/api/session/face-confirm",
                        body={"candidateToken": cand["candidateToken"]})
    if not check(status == 200, "กด 'ใช่' แล้วเปิดเซสชันได้", "HTTP 200", f"HTTP {status} {sess}"):
        return

    student = sess.get("student") or {}
    check(student.get("restricted") is False,
          "เซสชันจากใบหน้าไม่ถูกจำกัดสิทธิ", "restricted=False", str(student.get("restricted")))
    check("••••" in (student.get("studentIdMasked") or ""),
          "รหัสนักศึกษาถูกปิดบัง", "ขึ้นต้นด้วย ••••", str(student.get("studentIdMasked")))
    check(target not in json.dumps(sess, ensure_ascii=False),
          "ไม่มีรหัสนักศึกษาเต็มหลุดออกมา", "ไม่พบรหัสเต็ม", "พบรหัสเต็มใน response")

    status, _ = call("POST", "/api/session/face-confirm",
                     body={"candidateToken": cand["candidateToken"]})
    check(status == 410, "โทเค็นใช้ซ้ำไม่ได้", "HTTP 410", f"HTTP {status}")

    status, sched = call("GET", "/api/me/schedule", token=sess["token"])
    check(status == 200, "ดึงตารางเรียนของตนเองได้", "HTTP 200", f"HTTP {status}")
    check("isSynthetic" in (sched or {}),
          "ตารางเรียนบอกได้ว่าเป็นข้อมูลสมมติหรือไม่ (ของคนนี้ ไม่ใช่ของทั้งระบบ)",
          "มีฟิลด์ isSynthetic", str(list(sched or {})))
    call("DELETE", "/api/session", token=sess["token"])


def uc02_keypad() -> None:
    case("UC-02", "ระบบจำใบหน้าไม่ได้ → กรอกรหัสนักศึกษา")

    students = pick_students(2)
    if len(students) < 2:
        check(False, "มีนักศึกษาพอสำหรับทดสอบ", "อย่างน้อย 2 คน", f"{len(students)} คน")
        return

    status, sess = login_student(students[1])
    if not check(status == 200, "เข้าสู่ระบบด้วยรหัสนักศึกษาได้", "HTTP 200", f"HTTP {status} {sess}"):
        return

    student = sess.get("student") or {}
    check(sess.get("restricted") is True,
          "โหมดกรอกรหัสถูกทำเครื่องหมายว่าไม่ยืนยันตัวตน", "restricted=True", str(sess.get("restricted")))
    check(student.get("advisor") is None,
          "โหมดนี้ไม่เปิดเผยชื่ออาจารย์ที่ปรึกษา", "advisor=None", str(student.get("advisor")))

    status, _ = call("GET", "/api/me/schedule", token=sess["token"])
    check(status == 200, "ยังดูตารางเรียนได้", "HTTP 200", f"HTTP {status}")

    status, _ = call("DELETE", "/api/me/face", token=sess["token"])
    check(status == 403, "ลบข้อมูลใบหน้าไม่ได้ในโหมดนี้", "HTTP 403", f"HTTP {status}")

    status, body = login_student("0000000000")
    check(status == 404, "รหัสที่ไม่มีในระบบถูกปฏิเสธ", "HTTP 404", f"HTTP {status}")
    call("DELETE", "/api/session", token=sess["token"])


def uc03_enrolment() -> None:
    case("UC-03", "ลงทะเบียนใบหน้าครั้งแรก")

    status, body = call("POST", "/api/face/enroll/begin", body={"agreed": False})
    check(status == 400, "ไม่ยินยอมแล้วเริ่มถ่ายไม่ได้", "HTTP 400", f"HTTP {status} {body}")

    status, body = call("POST", "/api/face/enroll/begin", body={"agreed": True})
    if not check(status == 200, "ยินยอมแล้วเริ่มถ่ายได้ทันที (ยังไม่ต้องรู้ว่าเป็นใคร)",
                 "HTTP 200", f"HTTP {status} {body}"):
        return

    status, worker = call("GET", "/api/face/status")
    check(worker.get("mode") == "enrolling", "เซิร์ฟเวอร์เข้าสู่โหมดเก็บตัวอย่างใบหน้า",
          "mode=enrolling", str(worker.get("mode")))

    status, body = call("POST", "/api/face/enroll/complete",
                        body={"pendingToken": "โทเค็นปลอม", "studentId": "6604101336"})
    check(status == 410, "โทเค็นใบหน้าที่ไม่มีอยู่จริงใช้ไม่ได้", "HTTP 410", f"HTTP {status}")

    call("POST", "/api/face/enroll/cancel", body={})
    status, worker = call("GET", "/api/face/status")
    check(worker.get("mode") != "enrolling", "ยกเลิกแล้วออกจากโหมดเก็บตัวอย่าง",
          "mode != enrolling", str(worker.get("mode")))


def uc04_anonymous() -> None:
    case("UC-04", "ใช้งานแบบไม่ระบุตัวตน")

    status, sess = call("POST", "/api/session/anonymous")
    if not check(status == 200, "เปิดเซสชันแบบไม่ระบุตัวตนได้", "HTTP 200", f"HTTP {status}"):
        return
    check(sess.get("student") is None, "เซสชันนี้ไม่ผูกกับนักศึกษาคนใด", "student=None", str(sess.get("student")))

    token = sess["token"]
    status, res = call("POST", "/api/assistant/ask", token=token,
                       body={"questionId": "next-class"})
    answer = (res or {}).get("answer", {})
    check(answer.get("needAuth") is True,
          "คำถามที่ต้องใช้ข้อมูลส่วนบุคคลถูกปฏิเสธพร้อมคำอธิบาย",
          "needAuth=True", json.dumps(answer, ensure_ascii=False)[:80])

    status, res = call("POST", "/api/assistant/ask", token=token,
                       body={"questionId": "office-contact"})
    answer = (res or {}).get("answer", {})
    check(answer.get("source") == "db", "คำถามทั่วไปยังตอบได้", "source=db", str(answer.get("source")))

    status, _ = call("GET", "/api/me/schedule", token=token)
    check(status == 401, "ขอตารางเรียนด้วยเซสชันไม่ระบุตัวตนไม่ได้", "HTTP 401", f"HTTP {status}")
    call("DELETE", "/api/session", token=token)


def uc05_tap_questions(token: str) -> None:
    case("UC-05", "ถามด้วยการแตะปุ่มคำถามยอดนิยม")

    status, boot = call("GET", "/api/bootstrap")
    questions = {q["id"]: q for q in (boot or {}).get("quickQuestions", [])}
    check(len(questions) > 0, "มีคำถามยอดนิยมในระบบ", "อย่างน้อย 1 ข้อ", f"{len(questions)} ข้อ")

    for qid, want in (("next-class", "db"), ("room-floor", "db"),
                      ("exam-subject", "db"), ("contact-teacher", "db")):
        if qid not in questions:
            continue
        status, res = call("POST", "/api/assistant/ask", token=token,
                           body={"questionId": qid, "channel": "แตะ"})
        answer = (res or {}).get("answer", {})
        check(answer.get("source") == want,
              f"'{questions[qid]['label']}' ตอบจากฐานข้อมูล ไม่ผ่าน AI",
              f"source={want}", f"source={answer.get('source')} · {answer.get('title')}")
        check(bool(answer.get("title")), f"'{questions[qid]['label']}' มีหัวข้อคำตอบ",
              "มีข้อความ", str(answer.get("title")))


def uc06_typed(token: str) -> None:
    case("UC-06", "ถามด้วยการพิมพ์ข้อความ")

    for text, want_source in (
        ("คาบต่อไปเรียนที่ห้องไหน", "db"),
        ("ห้องนี้อยู่ชั้นไหน", "db"),
        ("ขอกำหนดสอบหน่อย", "db"),
    ):
        status, res = call("POST", "/api/assistant/ask", token=token,
                           body={"text": text, "channel": "พิมพ์"})
        answer = (res or {}).get("answer", {})
        intent = (res or {}).get("intent", {})
        check(answer.get("source") == want_source,
              f"'{text}' ไปที่ฐานข้อมูล ไม่ถูกส่งให้ AI เดา",
              f"source={want_source}",
              f"source={answer.get('source')} · วิธีตีความ {intent.get('method')}")

    status, res = call("POST", "/api/assistant/ask", token=token, body={"text": "   "})
    check(status == 400, "ข้อความว่างถูกปฏิเสธ", "HTTP 400", f"HTTP {status}")

    status, res = call("POST", "/api/assistant/ask", token=token, body={})
    check(status == 400, "ไม่ส่งคำถามมาเลยถูกปฏิเสธ", "HTTP 400", f"HTTP {status}")

    status, res = call("POST", "/api/assistant/ask", token=token,
                       body={"text": "ก" * 400, "channel": "พิมพ์"})
    check(status == 422, "ข้อความยาวเกินกำหนดถูกปฏิเสธ", "HTTP 422", f"HTTP {status}")


def uc08_unknown(token: str) -> None:
    case("UC-08", "ถามคำถามที่ไม่มีคำตอบในระบบ")

    status, res = call("POST", "/api/assistant/ask", token=token,
                       body={"questionId": "scholarship-detail"})
    answer = (res or {}).get("answer", {})
    check(answer.get("source") == "none", "ตอบว่าไม่พบข้อมูล ไม่เดาคำตอบ",
          "source=none", str(answer.get("source")))
    lines = " ".join(answer.get("lines") or [])
    check("@" in lines or "โทร" in lines, "เสนอช่องทางติดต่อสาขาแทน",
          "มีอีเมลหรือเบอร์โทร", lines[:80])

    status, res = call("POST", "/api/assistant/ask", token=token,
                       body={"text": "ราคาทองคำวันนี้เท่าไร", "channel": "พิมพ์"})
    answer = (res or {}).get("answer", {})
    check(answer.get("source") == "none", "คำถามนอกเรื่องไม่ถูกเดาคำตอบ",
          "source=none", f"source={answer.get('source')} · {answer.get('title')}")


def uc09_offline(token: str) -> None:
    case("UC-09", "ใช้งานขณะอินเทอร์เน็ตขัดข้อง")

    status, res = call("POST", "/api/assistant/ask", token=token,
                       body={"questionId": "next-class", "online": False})
    answer = (res or {}).get("answer", {})
    check(answer.get("source") == "db", "ตารางเรียนยังตอบได้ตอนออฟไลน์",
          "source=db", str(answer.get("source")))

    status, res = call("POST", "/api/assistant/ask", token=token,
                       body={"questionId": "add-drop", "online": False})
    answer = (res or {}).get("answer", {})
    check(answer.get("offlineBlocked") is True, "คำถามที่ต้องใช้ AI ถูกปิดพร้อมคำอธิบาย",
          "offlineBlocked=True", json.dumps(answer, ensure_ascii=False)[:90])

    status, res = call("POST", "/api/assistant/ask", token=token,
                       body={"text": "ประวัติของสาขาเป็นมายังไง", "online": False, "channel": "พิมพ์"})
    answer = (res or {}).get("answer", {})
    check(answer.get("offlineBlocked") is True,
          "คำถามปลายเปิดที่พิมพ์เองก็ถูกปิดตอนออฟไลน์",
          "offlineBlocked=True", json.dumps(answer, ensure_ascii=False)[:90])


def uc10_privacy() -> None:
    case("UC-10", "ข้อมูลส่วนบุคคลต้องปิดก่อนยืนยันตัวตน")

    for path in ("/api/me", "/api/me/schedule", "/api/me/exams", "/api/me/face"):
        status, _ = call("GET", path)
        check(status == 401, f"{path} ปฏิเสธคำขอที่ไม่มีเซสชัน", "HTTP 401", f"HTTP {status}")

    status, _ = call("GET", "/api/me/schedule", token="not-a-real-token")
    check(status == 401, "โทเค็นมั่วถูกปฏิเสธ", "HTTP 401", f"HTTP {status}")

    status, boot = call("GET", "/api/bootstrap")
    dumped = json.dumps(boot, ensure_ascii=False)
    check(status == 200 and "student" not in dumped.lower(),
          "ข้อมูลตั้งต้นของตู้ไม่มีข้อมูลนักศึกษาปนมา", "ไม่มีคำว่า student", "พบคำว่า student")


def uc11_self_delete() -> None:
    case("UC-11", "นักศึกษาลบข้อมูลใบหน้าของตนเองที่ตู้")

    students = pick_students(3)
    if not students:
        check(False, "มีนักศึกษาในระบบ", "อย่างน้อย 1 คน", "0 คน")
        return

    status, sess = login_student(students[0])
    if status != 200:
        check(False, "เตรียมเซสชันได้", "HTTP 200", f"HTTP {status}")
        return

    status, face = call("GET", "/api/me/face", token=sess["token"])
    check(status == 200, "ดูสถานะข้อมูลใบหน้าของตนเองได้", "HTTP 200", f"HTTP {status}")
    check(face.get("canDelete") is False,
          "เซสชันแบบกรอกรหัสลบข้อมูลไม่ได้ และหน้าจอรู้ล่วงหน้า",
          "canDelete=False", str(face.get("canDelete")))

    status, _ = call("DELETE", "/api/me/face", token=sess["token"])
    check(status == 403, "เซิร์ฟเวอร์ปฏิเสธการลบจากเซสชันที่ไม่ได้ยืนยันด้วยใบหน้า",
          "HTTP 403", f"HTTP {status}")
    call("DELETE", "/api/session", token=sess["token"])


def uc13_session_expiry() -> None:
    case("UC-13", "ออกจากระบบแล้วเซสชันต้องใช้ไม่ได้ทันที")

    students = pick_students(1)
    if not students:
        return
    status, sess = login_student(students[0])
    if status != 200:
        check(False, "เตรียมเซสชันได้", "HTTP 200", f"HTTP {status}")
        return

    token = sess["token"]
    status, _ = call("GET", "/api/me/schedule", token=token)
    check(status == 200, "ก่อนออกจากระบบยังใช้ได้", "HTTP 200", f"HTTP {status}")

    call("DELETE", "/api/session", token=token)
    status, _ = call("GET", "/api/me/schedule", token=token)
    check(status == 401, "หลังออกจากระบบใช้ไม่ได้อีก", "HTTP 401", f"HTTP {status}")


def uc14_inactive() -> None:
    case("UC-14", "ผู้ที่ไม่ได้เป็นนักศึกษาแล้วใช้ตู้ไม่ได้")

    found = pick_inactive()
    if found is None:
        check(False, "มีนักศึกษาที่พ้นสภาพในระบบสำหรับทดสอบ", "อย่างน้อย 1 คน", "0 คน")
        return
    student_id, label = found

    status, body = login_student(student_id)
    check(status == 403, "เข้าใช้งานด้วยรหัสไม่ได้", "HTTP 403", f"HTTP {status}")
    detail = (body or {}).get("detail", "")
    check(label[:6] in detail if label else bool(detail),
          "ข้อความบอกสาเหตุจริง ไม่ใช่ข้อความกลาง ๆ",
          f"มีคำว่า '{label}'", detail[:70])

    status, body = call("POST", "/api/sim/face/recognized", body={"studentId": student_id})
    check(status == 200, "ระบบจำลองยังสร้างผลการรู้จำได้ (ใช้ทดสอบขั้นถัดไป)",
          "HTTP 200", f"HTTP {status}")
    if status == 200 and "candidateToken" in body:
        status, sess = call("POST", "/api/session/face-confirm",
                            body={"candidateToken": body["candidateToken"]})
        check(status in (403, 410),
              "ถึงจะจำหน้าได้ ก็เปิดเซสชันให้ผู้ที่พ้นสภาพไม่ได้",
              "HTTP 403 หรือ 410", f"HTTP {status} {json.dumps(sess, ensure_ascii=False)[:60]}")


def uc17_enroll_timeout() -> None:
    case("UC-17", "ผู้ใช้เดินจากไปกลางขั้นตอนลงทะเบียน")

    status, _ = call("POST", "/api/face/enroll/begin", body={"agreed": True})
    if status != 200:
        check(False, "เริ่มขั้นตอนถ่ายใบหน้าได้", "HTTP 200", f"HTTP {status}")
        return

    print("           (รอไม่เกิน 25 วินาทีเพื่อดูว่าระบบเลิกเองหรือไม่)")
    deadline = time.time() + 25
    mode = "enrolling"
    while time.time() < deadline:
        time.sleep(2)
        _, worker = call("GET", "/api/face/status")
        mode = worker.get("mode", "?")
        if mode != "enrolling":
            break

    check(mode != "enrolling",
          "ระบบเลิกเก็บตัวอย่างเองเมื่อไม่มีใครอยู่หน้ากล้อง",
          "mode != enrolling ภายใน 25 วินาที", f"mode={mode} หลังรอ 25 วินาที")

    call("POST", "/api/face/enroll/cancel", body={})


def uc20_stale_scan() -> None:
    case("UC-20", "ผู้ใช้เลิกรอสแกนแล้วไปทำอย่างอื่น")

    status, _ = call("POST", "/api/face/scan/start")
    if not check(status == 200, "เริ่มสแกนใบหน้าได้", "HTTP 200", f"HTTP {status}"):
        return

    _, worker = call("GET", "/api/face/status")
    check(worker.get("mode") == "scanning", "เซิร์ฟเวอร์เข้าสู่โหมดหาใบหน้า",
          "mode=scanning", str(worker.get("mode")))

    # หน้าเว็บสั่งหยุดเมื่อผู้ใช้ออกจากหน้าสแกน
    status, _ = call("POST", "/api/face/scan/stop")
    check(status == 200, "สั่งหยุดสแกนได้", "HTTP 200", f"HTTP {status}")

    time.sleep(0.5)
    _, worker = call("GET", "/api/face/status")
    check(worker.get("mode") != "scanning",
          "กล้องเลิกหาใบหน้าทันที ไม่ทำงานต่อจนหมดเวลา",
          "mode != scanning", str(worker.get("mode")))


def uc19_registry() -> None:
    case("UC-19", "ทะเบียนผู้ลงทะเบียนใบหน้า")

    from app import db as db_module, repo

    conn = db_module.connect()
    try:
        registry = repo.registration_registry(conn)
        check(isinstance(registry, list), "อ่านทะเบียนได้", "รายการ", type(registry).__name__)

        total = conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]
        active = conn.execute("SELECT COUNT(*) c FROM students WHERE active = 1").fetchone()["c"]
        check(total > 0, "มีนักศึกษาในระบบ", "มากกว่า 0", str(total))
        print(f"           นักศึกษา {total} คน · ใช้ตู้ได้ {active} คน · ลงทะเบียนใบหน้าแล้ว {len(registry)} คน")

        orphans = repo.orphan_consents(conn)
        check(not orphans, "ไม่มีความยินยอมค้างโดยไม่มีข้อมูลผูกอยู่",
              "0 รายการ", f"{len(orphans)} รายการ")

        leaked = conn.execute(
            """SELECT COUNT(*) c FROM face_embeddings f
               LEFT JOIN consents c2 ON c2.id = f.consent_id AND c2.revoked_at IS NULL
               WHERE c2.id IS NULL"""
        ).fetchone()["c"]
        check(leaked == 0, "ไม่มีเวกเตอร์ใบหน้าที่ความยินยอมถูกถอนแล้ว",
              "0 รายการ", f"{leaked} รายการ")
    finally:
        conn.close()


# ------------------------------------------------------------
CASES = {
    "UC-01": ("นักศึกษาที่ลงทะเบียนใบหน้าแล้ว ยืนหน้าตู้", uc01_recognised_face),
    "UC-02": ("ระบบจำใบหน้าไม่ได้ → กรอกรหัสนักศึกษา", uc02_keypad),
    "UC-03": ("ลงทะเบียนใบหน้าครั้งแรก", uc03_enrolment),
    "UC-04": ("ใช้งานแบบไม่ระบุตัวตน", uc04_anonymous),
    "UC-05": ("ถามด้วยการแตะปุ่มคำถามยอดนิยม", None),
    "UC-06": ("ถามด้วยการพิมพ์ข้อความ", None),
    "UC-08": ("ถามคำถามที่ไม่มีคำตอบในระบบ", None),
    "UC-09": ("ใช้งานขณะอินเทอร์เน็ตขัดข้อง", None),
    "UC-10": ("ข้อมูลส่วนบุคคลต้องปิดก่อนยืนยันตัวตน", uc10_privacy),
    "UC-11": ("นักศึกษาลบข้อมูลใบหน้าของตนเองที่ตู้", uc11_self_delete),
    "UC-13": ("ออกจากระบบแล้วเซสชันใช้ไม่ได้ทันที", uc13_session_expiry),
    "UC-14": ("ผู้ที่ไม่ได้เป็นนักศึกษาแล้วใช้ตู้ไม่ได้", uc14_inactive),
    "UC-17": ("ผู้ใช้เดินจากไปกลางขั้นตอนลงทะเบียน", uc17_enroll_timeout),
    "UC-19": ("ทะเบียนผู้ลงทะเบียนใบหน้า", uc19_registry),
    "UC-20": ("ผู้ใช้เลิกรอสแกนแล้วไปทำอย่างอื่น", uc20_stale_scan),
}

# กรณีที่ต้องใช้เซสชันของนักศึกษาที่ยืนยันตัวตนแล้ว
WITH_SESSION = {
    "UC-05": uc05_tap_questions,
    "UC-06": uc06_typed,
    "UC-08": uc08_unknown,
    "UC-09": uc09_offline,
}


def main() -> int:
    global BASE

    parser = argparse.ArgumentParser(description="ทดสอบกรณีการใช้งานของตู้บริการข้อมูล")
    parser.add_argument("--only", metavar="UC-xx", help="ทดสอบเฉพาะกรณีเดียว")
    parser.add_argument("--list", action="store_true", help="แสดงรายการกรณีทั้งหมด")
    parser.add_argument("--base", default=BASE)
    args = parser.parse_args()

    if args.list:
        for code, (title, _) in CASES.items():
            print(f"  {code}  {title}")
        return 0

    BASE = args.base

    status, health = call("GET", "/api/health")
    if status != 200:
        print(f"ติดต่อเซิร์ฟเวอร์ที่ {BASE} ไม่ได้ — เปิดเซิร์ฟเวอร์ก่อนแล้วลองใหม่")
        return 2

    print(f"ทดสอบกับ {BASE}")
    print(f"ผู้ช่วย AI: {'พร้อมใช้งาน' if health.get('aiEnabled') else 'ปิดอยู่ (ไม่มีกุญแจ)'}")

    wanted = [args.only] if args.only else list(CASES)

    # เตรียมเซสชันกลางไว้ใช้กับกรณีถาม–ตอบ
    shared_token = None
    if any(c in WITH_SESSION for c in wanted):
        students = pick_students(1)
        if students:
            st, sess = login_student(students[0])
            if st == 200:
                shared_token = sess["token"]

    for code in wanted:
        if code not in CASES:
            print(f"ไม่รู้จักกรณี {code}")
            return 1
        title, fn = CASES[code]
        if fn is not None:
            fn()
        elif code in WITH_SESSION:
            if shared_token is None:
                case(code, title)
                check(False, "เตรียมเซสชันสำหรับทดสอบได้", "มีนักศึกษาที่ใช้ตู้ได้", "ไม่มี")
            else:
                WITH_SESSION[code](shared_token)

    if shared_token:
        call("DELETE", "/api/session", token=shared_token)

    failed = [(c, n, d) for c, ok, n, d in _results if not ok]
    print(f"\n{'=' * 60}")
    print(f"ผ่าน {len(_results) - len(failed)}/{len(_results)} ข้อ")
    if failed:
        print("\nกรณีที่ต้องแก้")
        for code, name, detail in failed:
            print(f"  {code}  {name}")
            print(f"        {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
