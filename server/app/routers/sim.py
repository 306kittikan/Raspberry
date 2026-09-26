"""จำลองเหตุการณ์จากกล้อง/ไมโครโฟน สำหรับพัฒนาและสาธิตโดยไม่ต้องมีฮาร์ดแวร์

เส้นทางเหล่านี้เปิดเฉพาะเมื่อ KIOSK_SIM=1 เท่านั้น
ตอนติดตั้งใช้งานจริงบนตู้ต้องปิด มิฉะนั้นใครก็ยิง /api/sim/face/recognized
เพื่อสวมรอยเป็นนักศึกษาคนใดก็ได้

หน้าเว็บเรียก API ชุดเดียวกันทั้งตอนจำลองและตอนใช้กล้องจริง
เมื่อกล้องมาถึงจึงเปลี่ยนแค่ "ผู้ผลิตเหตุการณ์" ไม่ต้องแก้หน้าจอ
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from .. import repo
from .. import session as session_store
from ..deps import Db
from ..events import hub

router = APIRouter(prefix="/api/sim", tags=["sim"])


class RecognizeIn(BaseModel):
    studentId: str | None = None   # ไม่ระบุ = ใช้คนแรกในฐานข้อมูล
    score: float = 0.62


@router.get("/students")
def list_students(conn: Db) -> dict:
    """รายชื่อสำหรับแผงทดสอบ — มีรหัสเต็มจึงเปิดเฉพาะโหมดจำลอง"""
    rows = conn.execute(
        "SELECT student_id, name FROM students ORDER BY student_id"
    ).fetchall()
    return {"students": [{"studentId": r["student_id"], "name": r["name"]} for r in rows]}


@router.post("/face/recognized")
async def face_recognized(body: RecognizeIn, conn: Db) -> dict:
    """จำลองว่ากล้องจำใบหน้าได้ → สร้าง candidate ให้ผู้ใช้กดยืนยัน"""
    if body.studentId:
        row = repo.find_student_by_code(conn, body.studentId)
    else:
        row = conn.execute("SELECT * FROM students ORDER BY id LIMIT 1").fetchone()

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบนักศึกษาที่ระบุ")

    cand = session_store.store.offer_candidate(row["id"], body.score)
    # หมายเหตุ: เส้นทางจำลองสร้างผลการรู้จำให้ใครก็ได้ รวมถึงผู้ที่พ้นสภาพ
    # เพื่อให้ทดสอบได้ว่าด่านที่ /api/session/face-confirm ทำงานจริง
    # ตัวรู้จำใบหน้าของจริงจะไม่ส่งผลแบบ recognized ให้ผู้ที่พ้นสภาพตั้งแต่ต้นทาง
    payload = {
        "result": "recognized",
        "candidateToken": cand.token,
        "name": row["name"],
        "score": body.score,
    }
    await hub.broadcast("face", payload)
    return payload


@router.post("/face/{result}")
async def face_problem(result: str) -> dict:
    """จำลองกรณีผิดปกติ: unknown | multi | notfound | camera_error"""
    allowed = {"unknown", "multi", "notfound", "camera_error"}
    if result not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"รองรับเฉพาะ {', '.join(sorted(allowed))}"
        )
    await hub.broadcast("face", {"result": result})
    return {"result": result}


@router.post("/presence/{state}")
async def presence(state: str) -> dict:
    """จำลองเซ็นเซอร์ตรวจจับผู้ใช้: detected | away"""
    if state not in {"detected", "away"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "รองรับเฉพาะ detected | away")
    await hub.broadcast("presence", {"state": state})
    return {"state": state}


class VoiceIn(BaseModel):
    transcript: str | None = None
    questionId: str | None = None


@router.post("/voice/{state}")
async def voice(state: str, body: VoiceIn | None = None) -> dict:
    """จำลองไมโครโฟน: listening | processing | transcript | unclear"""
    allowed = {"listening", "processing", "transcript", "unclear"}
    if state not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"รองรับเฉพาะ {', '.join(sorted(allowed))}"
        )
    payload: dict = {"state": state}
    if body is not None:
        if body.transcript:
            payload["transcript"] = body.transcript
        if body.questionId:
            payload["questionId"] = body.questionId
    await hub.broadcast("voice", payload)
    return payload
