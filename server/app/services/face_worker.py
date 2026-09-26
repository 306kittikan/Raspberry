"""วงจรทำงานของกล้อง: ตรวจจับคน → รู้จำใบหน้า → ลงทะเบียนใบหน้า

ทำงานในเธรดของตัวเอง เพราะการประมวลผลภาพเป็นงานที่บล็อก
และจะทำให้เซิร์ฟเวอร์หยุดตอบคำขออื่นถ้ารันในลูปหลัก
เหตุการณ์ที่เกิดขึ้นถูกส่งกลับเข้าลูป asyncio เพื่อกระจายผ่าน WebSocket

สถานะการทำงาน
  idle       เฝ้าดูว่ามีคนเดินมาหน้าตู้หรือไม่ (ใช้ปลุกจอจากโหมดพักลึก)
  scanning   กำลังหาว่าคนที่ยืนอยู่คือใคร
  enrolling  กำลังเก็บตัวอย่างใบหน้าเพื่อลงทะเบียน
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from .. import config
from ..events import hub
from ..session import store as session_store
from . import face
from .camera import camera

log = logging.getLogger("kiosk.face.worker")

# ระยะเวลาที่ยอมให้หาใบหน้าไม่เจอก่อนเสนอทางเลือกอื่น (ตรงกับที่ระบุในเอกสาร)
SCAN_TIMEOUT_S = 10.0
# ไม่มีใครอยู่หน้าตู้นานเท่านี้ถือว่าเดินไปแล้ว
PRESENCE_GONE_S = 3.0
# จำนวนตัวอย่างที่ต้องเก็บให้ได้ตอนลงทะเบียน
ENROLL_SAMPLES = 8
# เว้นระยะระหว่างตัวอย่าง เพื่อให้ได้ใบหน้าหลายมุมแทนที่จะเป็นเฟรมติดกัน
ENROLL_GAP_S = 0.35
# ตัวอย่างต้องสอดคล้องกันอย่างน้อยเท่านี้ ไม่งั้นให้ถ่ายใหม่
ENROLL_MIN_QUALITY = 0.60


@dataclass(slots=True)
class _EnrollJob:
    """งานเก็บตัวอย่างใบหน้าหนึ่งครั้ง

    ตอนเริ่มยังไม่รู้ว่าเป็นของใคร เพราะผู้ใช้ถ่ายใบหน้าก่อนแล้วค่อยกรอกรหัสนักศึกษา
    เวกเตอร์ที่ได้จึงถูกพักไว้ในหน่วยความจำ รอจนกว่าจะรู้ตัวตนจึงเขียนลงฐานข้อมูล
    """

    consent_at: datetime
    policy_version: str
    samples: list[np.ndarray] = field(default_factory=list)
    last_sample_at: float = 0.0


class FaceWorker:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._conn_factory = None

        self._lock = threading.Lock()
        self._mode = "idle"                       # idle | scanning | enrolling
        self._scan_started_at = 0.0
        self._enroll: _EnrollJob | None = None
        self._present = False
        self._last_seen_at = 0.0
        self._last_multi_at = 0.0
        self._fps_ms = 0.0

    # ------------------------------------------------------------
    # วงจรชีวิต
    # ------------------------------------------------------------
    def start(self, loop: asyncio.AbstractEventLoop, conn_factory) -> bool:
        """conn_factory สร้างการเชื่อมต่อฐานข้อมูลใหม่สำหรับเธรดนี้

        SQLite ห้ามใช้การเชื่อมต่อเดียวกันข้ามเธรด จึงต้องเปิดของตัวเอง
        """
        if not camera.start():
            return False
        if not face.engine.load():
            return False

        self._loop = loop
        self._conn_factory = conn_factory
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="face-worker", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        camera.stop()

    # ------------------------------------------------------------
    # คำสั่งจาก API
    # ------------------------------------------------------------
    def begin_scan(self) -> None:
        with self._lock:
            self._mode = "scanning"
            self._scan_started_at = time.time()
            self._enroll = None

    def end_scan(self) -> None:
        with self._lock:
            if self._mode == "scanning":
                self._mode = "idle"

    def begin_enroll(self, consent_at: datetime, policy_version: str) -> None:
        with self._lock:
            self._mode = "enrolling"
            self._enroll = _EnrollJob(consent_at=consent_at, policy_version=policy_version)

    def cancel_enroll(self) -> None:
        with self._lock:
            if self._mode == "enrolling":
                self._mode = "idle"
                self._enroll = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self._mode,
                "present": self._present,
                "modelReady": face.engine.ready,
                "modelError": face.engine.error,
                "detectMs": round(self._fps_ms),
                "camera": camera.status(),
            }

    # ------------------------------------------------------------
    # ส่งเหตุการณ์กลับเข้าลูป asyncio
    # ------------------------------------------------------------
    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(hub.broadcast(kind, payload), self._loop)

    # ------------------------------------------------------------
    # ลูปหลัก
    # ------------------------------------------------------------
    def _run(self) -> None:
        conn: sqlite3.Connection = self._conn_factory()
        last_seq = -1
        log.info("เริ่มทำงานกล้องและการรู้จำใบหน้า")

        try:
            while not self._stop.is_set():
                frame, seq = camera.wait_for_frame(last_seq, timeout=1.0)
                if frame is None:
                    if not camera.available:
                        self._emit("face", {"result": "camera_error",
                                            "detail": camera.error or "กล้องไม่พร้อมใช้งาน"})
                        break
                    continue
                last_seq = seq

                t0 = time.perf_counter()
                faces = face.engine.detect(frame)
                self._fps_ms = (time.perf_counter() - t0) * 1000

                self._update_presence(bool(faces))

                with self._lock:
                    mode = self._mode

                if mode == "scanning":
                    self._handle_scan(conn, faces)
                elif mode == "enrolling":
                    self._handle_enroll(conn, faces)
                else:
                    # โหมดเฝ้าดู ไม่ต้องประมวลผลถี่ ประหยัดซีพียูของ Raspberry Pi
                    time.sleep(0.25)
        except Exception:  # noqa: BLE001
            log.exception("ลูปกล้องหยุดทำงาน")
        finally:
            conn.close()
            log.info("หยุดการทำงานของกล้อง")

    # ------------------------------------------------------------
    def _update_presence(self, seen: bool) -> None:
        now = time.time()
        if seen:
            self._last_seen_at = now
            if not self._present:
                self._present = True
                self._emit("presence", {"state": "detected"})
        elif self._present and now - self._last_seen_at > PRESENCE_GONE_S:
            self._present = False
            self._emit("presence", {"state": "away"})

    # ------------------------------------------------------------
    def _handle_scan(self, conn: sqlite3.Connection, faces: list[face.DetectedFace]) -> None:
        now = time.time()
        usable = [f for f in faces if not f.too_small]

        # พบหลายใบหน้า: ไม่แสดงข้อมูลใด ๆ และแจ้งให้ใช้ทีละคน
        if len(usable) > 1:
            if now - self._last_multi_at > 1.5:
                self._last_multi_at = now
                self._emit("face", {"result": "multi", "count": len(usable)})
            return

        if not usable:
            if faces:
                # เจอใบหน้าแต่เล็กเกินไป แปลว่ายืนไกล บอกให้เข้ามาใกล้
                self._emit("face", {"result": "too_far"})
            if now - self._scan_started_at > SCAN_TIMEOUT_S:
                with self._lock:
                    self._mode = "idle"
                self._emit("face", {"result": "notfound"})
            return

        probe = usable[0]
        result = face.match(probe.embedding, face.load_enrolled(conn))

        with self._lock:
            self._mode = "idle"

        if result.student_pk is None:
            log.info("จำใบหน้าไม่ได้ (%s score=%.3f)", result.reason, result.score)
            self._emit("face", {"result": "unknown", "reason": result.reason,
                                "score": round(result.score, 4)})
            return

        row = conn.execute(
            "SELECT name FROM students WHERE id = ?", (result.student_pk,)
        ).fetchone()
        if row is None:
            self._emit("face", {"result": "unknown", "reason": "missing_student"})
            return

        cand = session_store.offer_candidate(result.student_pk, result.score)
        log.info("จำใบหน้าได้: %s (score=%.3f margin=%.3f)",
                 row["name"], result.score, result.score - result.runner_up)
        self._emit("face", {
            "result": "recognized",
            "candidateToken": cand.token,
            "name": row["name"],
            "score": round(result.score, 4),
        })

    # ------------------------------------------------------------
    def _handle_enroll(self, conn: sqlite3.Connection, faces: list[face.DetectedFace]) -> None:
        with self._lock:
            job = self._enroll
        if job is None:
            return

        usable = [f for f in faces if not f.too_small]
        if len(usable) > 1:
            self._emit("enroll", {"state": "multi"})
            return
        if not usable:
            self._emit("enroll", {"state": "searching",
                                  "progress": self._enroll_progress(job)})
            return

        now = time.time()
        if now - job.last_sample_at < ENROLL_GAP_S:
            return

        job.samples.append(usable[0].embedding)
        job.last_sample_at = now
        progress = self._enroll_progress(job)

        if len(job.samples) < ENROLL_SAMPLES:
            self._emit("enroll", {"state": "capturing", "progress": progress})
            return

        # เก็บครบแล้ว — ตรวจคุณภาพก่อนพักไว้
        quality = face.sample_quality(job.samples)
        with self._lock:
            self._mode = "idle"
            self._enroll = None

        if quality < ENROLL_MIN_QUALITY:
            log.warning("ตัวอย่างใบหน้าไม่สอดคล้องกัน (quality=%.3f) ไม่เก็บไว้", quality)
            self._emit("enroll", {"state": "failed", "reason": "quality",
                                  "quality": round(quality, 3)})
            return

        vector = face.average_embedding(job.samples)

        # ใบหน้านี้ตรงกับคนที่ลงทะเบียนไว้แล้วหรือไม่
        # ตรวจตั้งแต่ตอนนี้เพื่อไม่ให้ผู้ใช้เสียเวลากรอกรหัสแล้วค่อยมาถูกปฏิเสธ
        clash = face.match(vector, face.load_enrolled(conn))
        if clash.student_pk is not None:
            log.warning("ใบหน้าที่ถ่ายตรงกับผู้ที่ลงทะเบียนแล้ว (score=%.3f) ปฏิเสธ", clash.score)
            self._emit("enroll", {"state": "failed", "reason": "duplicate"})
            return

        # พักไว้ในหน่วยความจำ ยังไม่เขียนลงดิสก์จนกว่าจะรู้ว่าเป็นของใคร
        pending = session_store.hold_enrollment(
            vector=vector,
            quality=quality,
            consent_at=job.consent_at,
            policy_version=job.policy_version,
        )
        log.info("ถ่ายใบหน้าเสร็จ (quality=%.3f) รอระบุตัวตน", quality)
        self._emit("enroll", {
            "state": "captured",
            "progress": 100,
            "pendingToken": pending.token,
            "quality": round(quality, 3),
        })

    @staticmethod
    def _enroll_progress(job: _EnrollJob) -> int:
        return int(len(job.samples) / ENROLL_SAMPLES * 100)


worker = FaceWorker()
