"""ตรวจจับและรู้จำใบหน้า

ใช้ InsightFace ชุด buffalo_s ผ่าน ONNX Runtime
  - SCRFD   ตรวจหาตำแหน่งใบหน้าในภาพ
  - ArcFace แปลงใบหน้าเป็นเวกเตอร์ 512 มิติที่ normalise แล้ว

สิ่งที่เก็บลงฐานข้อมูลคือ "เวกเตอร์" เท่านั้น ไม่มีการเก็บภาพหรือวิดีโอ
เวกเตอร์ย้อนกลับเป็นภาพใบหน้าไม่ได้ จึงเป็นข้อมูลที่เสี่ยงน้อยกว่าการเก็บภาพมาก
แต่ยังถือเป็นข้อมูลชีวภาพตาม พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคลฯ มาตรา 26
จึงต้องมีความยินยอมแบบชัดแจ้งเสมอ (บังคับไว้ที่ schema ของฐานข้อมูลแล้ว)

การเทียบใบหน้าใช้ cosine similarity เพราะเวกเตอร์ถูก normalise ไว้แล้ว
ผลคูณจุดจึงเท่ากับ cosine similarity โดยตรง
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np

from .. import config

log = logging.getLogger("kiosk.face")

EMBEDDING_DIM = 512
MODEL_TAG = f"insightface/{config.FACE_MODEL_PACK}"

# ใบหน้าที่เล็กกว่านี้แปลว่าผู้ใช้ยืนไกลเกินไป เวกเตอร์จะไม่แม่น
MIN_FACE_PIXELS = 80
# คะแนนความมั่นใจขั้นต่ำของตัวตรวจจับ
MIN_DET_SCORE = 0.55


@dataclass(slots=True)
class DetectedFace:
    bbox: tuple[int, int, int, int]
    det_score: float
    embedding: np.ndarray  # normalise แล้ว ความยาว 512

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]

    @property
    def too_small(self) -> bool:
        return min(self.width, self.height) < MIN_FACE_PIXELS


@dataclass(slots=True)
class MatchResult:
    student_pk: int | None
    score: float
    runner_up: float
    reason: str  # 'matched' | 'below_threshold' | 'ambiguous' | 'no_enrolled'


class FaceEngine:
    """โหลดโมเดลครั้งเดียวแล้วใช้ซ้ำ การโหลดใช้เวลาหลายวินาที"""

    def __init__(self) -> None:
        self._app: Any = None
        self._lock = threading.Lock()
        self._error: str | None = None

    @property
    def ready(self) -> bool:
        return self._app is not None

    @property
    def error(self) -> str | None:
        return self._error

    def load(self) -> bool:
        if self._app is not None:
            return True
        try:
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(
                name=config.FACE_MODEL_PACK,
                root=str(config.FACE_MODEL_DIR),
                providers=["CPUExecutionProvider"],
                # โหลดเฉพาะสองส่วนที่ใช้จริง ข้ามการทำนายอายุ/เพศ/จุดสังเกตบนใบหน้า
                # ซึ่งเป็นข้อมูลส่วนบุคคลที่โครงงานนี้ไม่มีความจำเป็นต้องประมวลผล
                allowed_modules=["detection", "recognition"],
            )
            app.prepare(ctx_id=-1, det_size=(320, 320))
            self._app = app
            self._error = None
            log.info("โหลดโมเดลรู้จำใบหน้า %s เรียบร้อย", MODEL_TAG)
            return True
        except Exception as exc:  # noqa: BLE001 — ไม่มีโมเดลต้องไม่ทำให้ตู้ล่ม
            self._error = str(exc)
            log.warning("โหลดโมเดลรู้จำใบหน้าไม่ได้: %s", exc)
            return False

    def detect(self, frame: np.ndarray) -> list[DetectedFace]:
        """หาใบหน้าทั้งหมดในเฟรม เรียงจากใหญ่ไปเล็ก

        เรียงตามขนาดเพราะใบหน้าที่ใหญ่ที่สุดคือคนที่ยืนใกล้ตู้ที่สุด
        """
        if self._app is None:
            return []
        with self._lock:  # ONNX Runtime session ใช้ข้ามเธรดพร้อมกันไม่ได้
            faces = self._app.get(frame)

        out: list[DetectedFace] = []
        for f in faces:
            if float(f.det_score) < MIN_DET_SCORE:
                continue
            x1, y1, x2, y2 = (int(v) for v in f.bbox)
            out.append(
                DetectedFace(
                    bbox=(x1, y1, x2, y2),
                    det_score=float(f.det_score),
                    embedding=np.asarray(f.normed_embedding, dtype=np.float32),
                )
            )
        out.sort(key=lambda d: d.width * d.height, reverse=True)
        return out


engine = FaceEngine()


# ------------------------------------------------------------
# การเก็บและเทียบเวกเตอร์
# ------------------------------------------------------------
def to_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype="<f4").tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="<f4")


def load_enrolled(conn: sqlite3.Connection) -> list[tuple[int, np.ndarray]]:
    """เวกเตอร์ทั้งหมดที่ยังมีความยินยอมอยู่

    การ JOIN กับ consents ที่ revoked_at IS NULL ทำให้ผู้ที่ถอนความยินยอม
    ถูกตัดออกจากการเทียบทันที แม้แถวจะยังไม่ถูกลบด้วยเหตุใดก็ตาม
    """
    rows = conn.execute(
        """
        SELECT f.student_id, f.vector
        FROM face_embeddings f
        JOIN consents c ON c.id = f.consent_id AND c.revoked_at IS NULL
        WHERE f.model = ?
        """,
        (MODEL_TAG,),
    ).fetchall()
    return [(r["student_id"], from_blob(r["vector"])) for r in rows]


def match(probe: np.ndarray, enrolled: list[tuple[int, np.ndarray]]) -> MatchResult:
    """หาว่าใบหน้าที่เห็นตรงกับใคร

    ตัดสินว่า "ตรง" ต่อเมื่อผ่านทั้งสองเงื่อนไข
      1. คะแนนสูงกว่าเกณฑ์  — กันการทักคนที่ไม่เคยลงทะเบียน
      2. ห่างจากอันดับสองพอสมควร — กันการจำสลับคนที่หน้าคล้ายกัน

    เงื่อนไขข้อสองสำคัญกับความเสี่ยง "ระบบรู้จำใบหน้าผิดคน" ที่ระบุไว้ในเอกสาร
    เพราะการทักผิดคนแล้วโชว์ตารางเรียนของคนอื่นคือการเปิดเผยข้อมูลส่วนบุคคล
    """
    if not enrolled:
        return MatchResult(None, 0.0, 0.0, "no_enrolled")

    # รวมเวกเตอร์ของคนเดียวกันหลายใบ โดยเก็บคะแนนสูงสุดของแต่ละคน
    best_by_student: dict[int, float] = {}
    for student_pk, vector in enrolled:
        score = float(np.dot(probe, vector))
        if score > best_by_student.get(student_pk, -1.0):
            best_by_student[student_pk] = score

    ranked = sorted(best_by_student.items(), key=lambda kv: kv[1], reverse=True)
    top_pk, top_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0

    if top_score < config.FACE_MATCH_THRESHOLD:
        return MatchResult(None, top_score, runner_up, "below_threshold")
    if top_score - runner_up < config.FACE_MATCH_MARGIN:
        return MatchResult(None, top_score, runner_up, "ambiguous")
    return MatchResult(top_pk, top_score, runner_up, "matched")


def average_embedding(samples: list[np.ndarray]) -> np.ndarray:
    """รวมหลายเวกเตอร์จากการถ่ายหลายมุมให้เป็นตัวแทนเดียว

    ค่าเฉลี่ยของเวกเตอร์ที่ normalise แล้วต้อง normalise ซ้ำ
    เพื่อให้ผลคูณจุดยังเท่ากับ cosine similarity
    """
    stacked = np.vstack(samples).astype(np.float32)
    mean = stacked.mean(axis=0)
    norm = np.linalg.norm(mean)
    if norm == 0:
        raise ValueError("เวกเตอร์ที่ได้ไม่ถูกต้อง")
    return (mean / norm).astype(np.float32)


def sample_quality(samples: list[np.ndarray]) -> float:
    """ความสอดคล้องกันของตัวอย่างที่เก็บมา (0–1)

    ถ้าแต่ละใบต่างกันมาก แปลว่าถ่ายติดคนละคนหรือภาพไม่ชัด
    ควรให้ถ่ายใหม่ดีกว่าบันทึกเวกเตอร์ที่เชื่อถือไม่ได้
    """
    if len(samples) < 2:
        return 1.0
    center = average_embedding(samples)
    return float(np.mean([np.dot(center, s) for s in samples]))
