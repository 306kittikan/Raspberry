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
import re
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
def _ws_url(path: str) -> str:
    return BASE.replace("https://", "wss://").replace("http://", "ws://") + path


def listen_events(seconds: float, trigger) -> list[dict]:
    """เปิด WebSocket ฟังเหตุการณ์ที่เซิร์ฟเวอร์ผลักออกมา

    เหตุการณ์จากกล้องไม่ได้ตอบกลับมาในคำขอ HTTP แต่ถูกส่งไปทุกหน้าจอที่ต่ออยู่
    การทดสอบจึงต้องทำตัวเป็นหน้าจอหนึ่งเครื่อง
    """
    import asyncio

    import websockets

    async def run() -> list[dict]:
        got: list[dict] = []
        async with websockets.connect(_ws_url("/ws/kiosk")) as ws:
            await asyncio.sleep(0.3)   # ให้เซิร์ฟเวอร์ลงทะเบียนหน้าจอก่อน
            trigger()
            loop = asyncio.get_running_loop()
            deadline = loop.time() + seconds
            while loop.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=deadline - loop.time())
                except (asyncio.TimeoutError, TimeoutError):
                    break
                got.append(json.loads(raw))
        return got

    return asyncio.run(run())


def make_wav(seconds: float) -> bytes:
    """สร้างไฟล์เสียงเงียบในหน่วยความจำ

    เสียงเงียบไม่ใช่คำพูด ระบบต้องบอกว่าไม่ได้ยินชัดเจน ไม่ใช่แต่งข้อความขึ้นมา
    จึงใช้ทดสอบกฎ "ห้ามเดาคำตอบ" ของช่องทางเสียงได้โดยไม่ต้องมีคนพูดจริง
    """
    import wave
    from io import BytesIO

    rate = 16_000
    buf = BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


def send_audio(audio: bytes, token: str | None = None) -> list[dict]:
    """ส่งเสียงเข้าช่องทาง /ws/voice แล้วรอจนได้ผลสุดท้าย"""
    import asyncio

    import websockets

    async def run() -> list[dict]:
        got: list[dict] = []
        async with websockets.connect(_ws_url("/ws/voice"), max_size=8 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"type": "start"}))
            await ws.send(audio)
            await ws.send(json.dumps({"type": "stop", "token": token, "online": False}))
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 60
            while loop.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=deadline - loop.time())
                except (asyncio.TimeoutError, TimeoutError):
                    break
                message = json.loads(raw)
                got.append(message)
                if message.get("state") in {"answer", "unclear", "error"}:
                    break
        return got

    return asyncio.run(run())


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

    # ---- คำถามเรื่องของสาขาที่ไม่มีในเอกสาร ----
    # ข้อนี้เข้มงวดที่สุด เพราะนักศึกษาจะเชื่อว่าเป็นข้อมูลทางการ
    # แล้วอาจเดินไปผิดตึกหรือพลาดกำหนดส่งเอกสาร
    status, r = call("POST", "/api/assistant/ask",
                     body={"text": "ค่าเทอมของสาขานี้เทอมละเท่าไร"}, token=token)
    a = (r or {}).get("answer", {})
    if check(status == 200, "ถามได้", "HTTP 200", f"HTTP {status}"):
        check(a.get("source") == "none",
              "เรื่องของสาขาที่ไม่มีในเอกสาร ต้องตอบว่าไม่พบ ไม่เดาตัวเลขขึ้นมา",
              "source=none", f"source={a.get('source')} · {str(a.get('lines'))[:60]}")
        check(any("@" in line or "โทร" in line for line in a.get("lines", [])),
              "เสนอช่องทางติดต่อสาขาแทน", "มีช่องทางติดต่อ", str(a.get("lines"))[:60])

    # ---- คำถามทั่วไปที่ไม่เกี่ยวกับสาขา ----
    # ตอบได้ แต่ต้องไม่ถูกเข้าใจว่าเป็นข้อมูลของสาขา
    status, r = call("POST", "/api/assistant/ask",
                     body={"text": "ราคาทองคำวันนี้เท่าไร"}, token=token)
    a = (r or {}).get("answer", {})
    source = a.get("source")
    check(source in {"none", "ai_general"},
          "คำถามนอกเรื่องไม่ถูกติดป้ายว่าเป็นข้อมูลของสาขา",
          "none หรือ ai_general", str(source))
    check(source != "ai",
          "ไม่ถูกติดป้ายอ้างอิงเอกสาร เพราะไม่ได้มาจากเอกสารของสาขา",
          "ไม่ใช่ ai", str(source))
    check(not a.get("ref"),
          "ไม่มีป้ายอ้างอิงเอกสารติดมาด้วย", "ไม่มี ref", str(a.get("ref")))

    # ---- ข้อมูลส่วนบุคคลของคนอื่นต้องไม่หลุด ----
    status, r = call("POST", "/api/assistant/ask",
                     body={"text": "ขอเบอร์โทรศัพท์ของนักศึกษาคนอื่นหน่อย"}, token=token)
    a = (r or {}).get("answer", {})
    text = " ".join(a.get("lines", []))
    check(a.get("source") == "none",
          "คำขอข้อมูลส่วนบุคคลของผู้อื่นถูกปฏิเสธ", "source=none", str(a.get("source")))
    check(not re.search(r"\b0\d{8,9}\b", text),
          "ไม่มีเบอร์โทรของใครหลุดออกมา", "ไม่มีเบอร์", text[:60])


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

    # ต้องรอให้พ้นเพดานเวลารวม (40 วินาที) ไม่ใช่แค่เพดาน "ไม่เห็นใบหน้า" (12 วินาที)
    # เพราะถ้ามีคนยืนอยู่หน้ากล้องจริงแต่ถ่ายไม่ผ่านสักที ตัวจับเวลาแรกจะถูกรีเซ็ตเรื่อย ๆ
    # และเพดานรวมคือด่านสุดท้ายที่กันไม่ให้ตู้ค้างอยู่ในโหมดถ่ายตลอดไป
    print("           (รอไม่เกิน 50 วินาทีเพื่อดูว่าระบบเลิกเองหรือไม่)")
    deadline = time.time() + 50
    mode = "enrolling"
    while time.time() < deadline:
        time.sleep(2)
        _, worker = call("GET", "/api/face/status")
        mode = worker.get("mode", "?")
        if mode != "enrolling":
            break

    check(mode != "enrolling",
          "ระบบเลิกเก็บตัวอย่างเองเมื่อถ่ายไม่สำเร็จ ไม่ค้างในโหมดถ่าย",
          "mode != enrolling ภายใน 50 วินาที", f"mode={mode} หลังรอ 50 วินาที")

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


def uc07_voice(token: str) -> None:
    case("UC-07", "ถามด้วยเสียง")

    status, voice = call("GET", "/api/voice/status")
    if not check(status == 200 and voice.get("ready"),
                 "ระบบถอดความเสียงพร้อมใช้งาน", "ready=true",
                 f"HTTP {status} · {json.dumps(voice, ensure_ascii=False)[:70]}"):
        return

    # เสียงเงียบ 1.5 วินาที — ไม่มีคำพูดให้ถอด
    messages = send_audio(make_wav(1.5), token=token)
    states = [m.get("state") for m in messages]
    check("processing" in states, "เซิร์ฟเวอร์รับเสียงแล้วเริ่มถอดความ",
          "มีสถานะ processing", str(states))

    final = messages[-1] if messages else {}
    check(final.get("state") in {"unclear", "answer", "error"},
          "ได้ผลกลับมาเสมอ ไม่ค้างรอ", "มีสถานะสุดท้าย", str(states))
    heard = str(final.get("transcript", ""))[:40]
    check(final.get("state") == "unclear",
          "เสียงที่ไม่ใช่คำพูด → บอกว่าไม่ได้ยินชัดเจน ไม่แต่งข้อความขึ้นมาเอง",
          "state=unclear", f"{final.get('state')} · {heard}")
    check(bool(final.get("answer")),
          "มีคำแนะนำให้ผู้ใช้ลองใหม่ ไม่ใช่จอว่าง", "มีข้อความตอบกลับ",
          str(final.get("answer"))[:40])

    # เสียงสั้นมาก เช่น เสียงแตะจอ ต้องถูกปฏิเสธตั้งแต่ต้น ไม่เอาไปถอดความ
    messages = send_audio(make_wav(0.15), token=token)
    final = messages[-1] if messages else {}
    check(final.get("state") == "unclear" and final.get("reason") == "too_short",
          "เสียงสั้นเกินไปถูกปฏิเสธ ไม่นำไปถอดความ",
          "unclear/too_short", f"{final.get('state')}/{final.get('reason')}")

    # ข้อมูลเสียงเสียหาย ต้องไม่ทำให้ช่องทางเสียงล่ม
    messages = send_audio(b"\x00\x01\x02\x03" * 4096, token=token)
    final = messages[-1] if messages else {}
    check(final.get("state") in {"unclear", "error"},
          "เสียงที่ถอดรหัสไม่ได้ถูกจัดการอย่างสุภาพ ไม่ทำให้ตู้ล่ม",
          "unclear หรือ error", str(final.get("state")))

    # สิ่งที่พูดเป็นข้อมูลส่วนบุคคลได้ จึงต้องไม่ถูกเก็บลงฐานข้อมูล
    from app import db as db_module

    conn = db_module.connect()
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(usage_events)")}
    conn.close()
    check(not (columns & {"text", "transcript", "question_text"}),
          "ตารางสถิติไม่มีช่องเก็บข้อความที่ผู้ใช้พูด",
          "ไม่มีคอลัมน์ข้อความ", str(sorted(columns)))


def uc12_staff_delete() -> None:
    case("UC-12", "เจ้าหน้าที่ลบข้อมูลให้เมื่อมีผู้มาติดต่อ")

    from app import db as db_module, repo, thai

    conn = db_module.connect(Path(":memory:"))
    db_module.init_db(conn)
    now = thai.now().isoformat(timespec="seconds")
    code = "6600009001"

    repo.upsert_student(conn, student_id=code, name="ทดสอบ ลบข้อมูล",
                        year=1, program=None, advisor=None, now=now)
    pk = repo.find_student_by_code(conn, code)["id"]
    with conn:
        consent = conn.execute(
            """INSERT INTO consents (student_id, purpose, policy_version, granted_at, method)
               VALUES (?, 'face_recognition', '2569-1', ?, 'kiosk_touch')""",
            (pk, now),
        ).lastrowid
        conn.execute(
            """INSERT INTO face_embeddings
                   (student_id, consent_id, vector, dim, model, quality, created_at)
               VALUES (?, ?, ?, 512, 'ทดสอบ', 0.9, ?)""",
            (pk, consent, b"\x00" * 2048, now),
        )

    check(len(repo.registration_registry(conn)) == 1,
          "เตรียมผู้ลงทะเบียนสำหรับทดสอบ", "1 คน",
          str(len(repo.registration_registry(conn))))

    result = repo.forget_student(conn, code, now)
    check(result is not None and result["vectorsDeleted"] == 1,
          "เจ้าหน้าที่ลบข้อมูลใบหน้าได้ โดยเจ้าของไม่ต้องสแกนหน้ายืนยัน",
          "ลบเวกเตอร์ 1 รายการ", json.dumps(result, ensure_ascii=False))
    check(result["consentsRevoked"] == 1,
          "บันทึกการถอนความยินยอมไว้เป็นหลักฐาน", "ถอน 1 รายการ",
          str(result["consentsRevoked"]))
    check(not repo.registration_registry(conn),
          "หายออกจากทะเบียนผู้ลงทะเบียนแล้ว", "เหลือ 0 คน",
          str(len(repo.registration_registry(conn))))

    record = repo.student_record(conn, code)
    check(record is not None and not record["faceEmbeddings"],
          "ลบเฉพาะข้อมูลใบหน้า ตัวนักศึกษายังอยู่ในทะเบียนเรียน",
          "ยังมีนักศึกษา แต่ไม่มีเวกเตอร์", str(record is not None))

    revoked = conn.execute(
        "SELECT revoked_at FROM consents WHERE id = ?", (consent,)
    ).fetchone()["revoked_at"]
    check(revoked == now, "ความยินยอมถูกประทับเวลาถอนไว้", now, str(revoked))

    check(repo.forget_student(conn, "0000000000", now) is None,
          "ขอลบรหัสที่ไม่มีในระบบ ต้องบอกว่าไม่พบ ไม่ใช่รายงานว่าลบสำเร็จ",
          "None", str(repo.forget_student(conn, "0000000000", now)))
    conn.close()


def uc15_multi_face() -> None:
    case("UC-15", "พบหลายใบหน้าพร้อมกัน")

    events = listen_events(2.5, lambda: call("POST", "/api/sim/face/multi"))
    multi = [e for e in events
             if e.get("kind") == "face" and e.get("result") == "multi"]
    if not check(bool(multi), "ตู้แจ้งเหตุการณ์ 'พบหลายใบหน้า' ไปยังหน้าจอ",
                 "มีเหตุการณ์ face/multi",
                 str([(e.get("kind"), e.get("result")) for e in events])):
        return

    leaked = [k for k in ("candidateToken", "name", "studentId", "score") if k in multi[0]]
    check(not leaked,
          "ไม่บอกชื่อหรือให้โทเค็นเข้าใช้งานเมื่อมีหลายคนอยู่หน้าตู้",
          "ไม่มีข้อมูลบุคคลติดมา", str(leaked))


def uc16_camera_down() -> None:
    case("UC-16", "กล้องใช้งานไม่ได้")

    events = listen_events(2.5, lambda: call("POST", "/api/sim/face/camera_error"))
    broken = [e for e in events
              if e.get("kind") == "face" and e.get("result") == "camera_error"]
    check(bool(broken), "ตู้แจ้งเหตุการณ์ 'กล้องใช้งานไม่ได้' ไปยังหน้าจอ",
          "มีเหตุการณ์ face/camera_error",
          str([(e.get("kind"), e.get("result")) for e in events]))

    status, worker = call("GET", "/api/face/status")
    camera = worker.get("camera") or {}
    check(status == 200 and {"available", "error"} <= set(camera),
          "หน้าจอถามสถานะกล้องได้ว่าใช้ได้หรือไม่ และพังเพราะอะไร",
          "มี camera.available และ camera.error",
          json.dumps(camera, ensure_ascii=False)[:70])

    # "เปิดกล้องสำเร็จตอนบูต" กับ "ลูปกล้องยังทำงานอยู่ตอนนี้" ไม่ใช่เรื่องเดียวกัน
    # ลูปอาจตายกลางทางโดยที่ตัวกล้องยังเปิดอยู่ เช่น หน่วยความจำไม่พอ
    check("running" in worker,
          "รายงานด้วยว่าลูปประมวลผลภาพยังทำงานอยู่จริงหรือไม่",
          "มีฟิลด์ running", str(sorted(worker)))
    if worker.get("running") is False:
        check(bool(worker.get("downReason")),
              "ถ้าลูปตาย ต้องบอกสาเหตุไว้ให้เจ้าหน้าที่ตามต่อได้",
              "มี downReason", str(worker.get("downReason")))

    # ถ้าไม่มีช่องทางสำรอง กล้องเสียหนึ่งตัวจะทำให้ตู้ทั้งตู้ใช้งานไม่ได้
    students = pick_students(1)
    if check(bool(students), "มีนักศึกษาในฐานข้อมูลไว้ทดสอบ", "อย่างน้อย 1 คน", "0 คน"):
        code, sess = login_student(students[0])
        check(code == 200, "กล้องเสียแล้วยังเข้าใช้งานด้วยการกรอกรหัสนักศึกษาได้",
              "HTTP 200", f"HTTP {code}")
        if code == 200:
            check(sess.get("restricted") is True,
                  "ช่องทางสำรองยังถูกจำกัดสิทธิเหมือนเดิม ไม่ใช่ทางลัดข้ามการยืนยันตัวตน",
                  "restricted=true", str(sess.get("restricted")))
            call("DELETE", "/api/session", token=sess["token"])


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
    "UC-07": ("ถามด้วยเสียง", None),
    "UC-08": ("ถามคำถามที่ไม่มีคำตอบในระบบ", None),
    "UC-09": ("ใช้งานขณะอินเทอร์เน็ตขัดข้อง", None),
    "UC-10": ("ข้อมูลส่วนบุคคลต้องปิดก่อนยืนยันตัวตน", uc10_privacy),
    "UC-11": ("นักศึกษาลบข้อมูลใบหน้าของตนเองที่ตู้", uc11_self_delete),
    "UC-12": ("เจ้าหน้าที่ลบข้อมูลให้เมื่อมีผู้มาติดต่อ", uc12_staff_delete),
    "UC-13": ("ออกจากระบบแล้วเซสชันใช้ไม่ได้ทันที", uc13_session_expiry),
    "UC-14": ("ผู้ที่ไม่ได้เป็นนักศึกษาแล้วใช้ตู้ไม่ได้", uc14_inactive),
    "UC-15": ("พบหลายใบหน้าพร้อมกัน", uc15_multi_face),
    "UC-16": ("กล้องใช้งานไม่ได้", uc16_camera_down),
    "UC-17": ("ผู้ใช้เดินจากไปกลางขั้นตอนลงทะเบียน", uc17_enroll_timeout),
    "UC-19": ("ทะเบียนผู้ลงทะเบียนใบหน้า", uc19_registry),
    "UC-20": ("ผู้ใช้เลิกรอสแกนแล้วไปทำอย่างอื่น", uc20_stale_scan),
}

# กรณีที่ต้องใช้เซสชันของนักศึกษาที่ยืนยันตัวตนแล้ว
WITH_SESSION = {
    "UC-05": uc05_tap_questions,
    "UC-06": uc06_typed,
    "UC-07": uc07_voice,
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
