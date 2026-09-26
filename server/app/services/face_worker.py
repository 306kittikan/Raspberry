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
# เลิกเก็บตัวอย่างเมื่อไม่เห็นใบหน้าติดต่อกันนานเท่านี้
# ตีความว่าผู้ใช้เดินจากไปแล้ว ซึ่งเป็นกรณีที่พบบ่อยที่สุด
ENROLL_NO_FACE_S = 12.0
# เพดานเวลารวม กันกรณีที่มีใบหน้าเข้า ๆ ออก ๆ จนไม่ครบสักที
# ถ้าไม่มีเพดาน ตู้จะค้างอยู่ในโหมดถ่ายตลอดไป กินซีพียูและบล็อกคนถัดไป
ENROLL_TIMEOUT_S = 40.0
# ส่งสถานะ "ยังหาใบหน้าไม่เจอ" ถี่แค่ไหน ไม่ต้องส่งทุกเฟรม
ENROLL_HINT_EVERY_S = 1.0
# เว้นช่วงก่อนลองกู้กล้องอีกครั้งหลังขัดข้อง
# กล้องที่ถูกถอดสายออกจะไม่กลับมา การลองใหม่ทุกครั้งที่มีคนกดจึงเปลืองเปล่า
# และการเปิดกล้องซ้ำ ๆ ทำให้คำขออื่นช้าตามไปด้วย
RESTART_COOLDOWN_S = 15.0


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
    started_at: float = 0.0
    last_face_at: float = 0.0
    last_hint_at: float = 0.0


class FaceWorker:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._conn_factory = None

        self._lock = threading.Lock()
        self._restart_lock = threading.Lock()
        self._running = False                     # ลูปกล้องยังมีชีวิตอยู่หรือไม่
        self._down_reason: str | None = None      # ลูปตายเพราะอะไร
        self._last_restart_at = 0.0
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
        # จำไว้ก่อนเปิดกล้อง เพื่อให้ ensure_running() กู้ได้ทีหลัง
        # แม้ตอนเปิดเครื่องยังไม่มีกล้องเสียบอยู่
        self._loop = loop
        self._conn_factory = conn_factory

        if not camera.start():
            self._down_reason = camera.error
            return False
        if not face.engine.load():
            self._down_reason = face.engine.error
            return False

        self._launch()
        return True

    def _launch(self) -> None:
        self._stop.clear()
        self._down_reason = None
        self._running = True   # ตั้งก่อนเริ่มเธรด กันไม่ให้มีคนสั่งเปิดซ้อนอีกตัว
        self._thread = threading.Thread(target=self._run, name="face-worker", daemon=True)
        self._thread.start()

    def ensure_running(self) -> tuple[bool, str | None]:
        """ลูปกล้องยังทำงานอยู่หรือไม่ ถ้าตายไปแล้วให้ลองกู้กลับมา

        ตู้เปิดต่อเนื่องหลายวัน ความขัดข้องชั่วคราว เช่น หน่วยความจำไม่พอ
        หรือสาย USB หลวม ต้องกู้เองได้ ไม่ใช่รอให้เจ้าหน้าที่มาเริ่มบริการใหม่
        คืนค่า (สำเร็จ, เหตุผลถ้าไม่สำเร็จ) ให้เส้นทาง API เอาไปบอกผู้ใช้
        """
        if self._running:
            return True, None
        if self._loop is None or self._conn_factory is None:
            return False, "ระบบกล้องยังไม่เริ่มทำงาน"

        def down() -> str:
            return self._down_reason or camera.error or "กล้องไม่พร้อมใช้งาน"

        # มีคนกำลังกู้อยู่แล้ว ไม่ต้องกู้ซ้อน
        if not self._restart_lock.acquire(blocking=False):
            return False, down()
        try:
            if self._running:
                return True, None
            now = time.time()
            if now - self._last_restart_at < RESTART_COOLDOWN_S:
                return False, down()
            self._last_restart_at = now

            camera.stop()
            if not camera.start():
                self._down_reason = camera.error
                return False, down()
            if not face.engine.load():
                self._down_reason = face.engine.error
                return False, down()

            self._launch()
            log.info("เริ่มการทำงานของกล้องใหม่หลังขัดข้อง")
            return True, None
        finally:
            self._restart_lock.release()

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
            now = time.time()
            self._enroll = _EnrollJob(
                consent_at=consent_at,
                policy_version=policy_version,
                started_at=now,
                last_face_at=now,
            )

    def cancel_enroll(self) -> None:
        with self._lock:
            if self._mode == "enrolling":
                self._mode = "idle"
                self._enroll = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self._mode,
                "running": self._running,
                "downReason": self._down_reason,
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
        self._running = True
        log.info("เริ่มทำงานกล้องและการรู้จำใบหน้า")

        try:
            while not self._stop.is_set():
                frame, seq = camera.wait_for_frame(last_seq, timeout=1.0)
                if frame is None:
                    if not camera.available:
                        self._down_reason = camera.error or "กล้องไม่พร้อมใช้งาน"
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
        except Exception as exc:  # noqa: BLE001 — กล้องล้มต้องไม่ทำให้ตู้ทั้งตู้ล่ม
            log.exception("ลูปกล้องหยุดทำงาน")
            self._down_reason = str(exc) or exc.__class__.__name__
        finally:
            conn.close()
            self._running = False
            self._abandon()

    def _abandon(self) -> None:
        """ลูปกล้องจบลงแล้ว ต้องไม่ทิ้งสถานะค้างไว้

        ถ้าปล่อยให้ mode ยังเป็น scanning หรือ enrolling หน้าจอจะหมุนรอผล
        ที่ไม่มีวันมาถึง เพราะไม่มีใครประมวลผลเฟรมให้อีกแล้ว
        และตัวจับเวลาทุกตัวก็อยู่ในลูปเดียวกันนั้น จึงไม่มีอะไรมาปลดล็อกให้
        ผู้ใช้จะติดอยู่หน้านั้นจนกว่าจะมีเจ้าหน้าที่มาเริ่มบริการใหม่
        """
        with self._lock:
            self._mode = "idle"
            self._enroll = None
            self._present = False
        log.info("หยุดการทำงานของกล้อง")

        if self._stop.is_set():
            return   # ปิดตามคำสั่งตอนปิดเซิร์ฟเวอร์ ไม่ต้องแจ้งหน้าจอ

        # แจ้งทุกหน้าจอให้สลับไปใช้การกรอกรหัสนักศึกษา
        self._emit("face", {"result": "camera_error",
                            "detail": self._down_reason or "กล้องหยุดทำงานกะทันหัน"})

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
            "SELECT name, active FROM students WHERE id = ?", (result.student_pk,)
        ).fetchone()
        if row is None:
            self._emit("face", {"result": "unknown", "reason": "missing_student"})
            return

        # จำหน้าได้ แต่เจ้าของหน้าไม่ได้เป็นนักศึกษาของสาขาแล้ว
        # ไม่เปิดเซสชันให้ และไม่บอกชื่อออกไป เพราะยังไม่มีใครยืนยันตัวตน
        if not row["active"]:
            log.info("จำใบหน้าได้แต่ผู้ใช้พ้นสภาพแล้ว (student_pk=%s)", result.student_pk)
            self._emit("face", {"result": "inactive"})
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

        now = time.time()
        usable = [f for f in faces if not f.too_small]
        if usable:
            job.last_face_at = now

        # เลิกเองเมื่อผู้ใช้เดินจากไป หรือถ่ายไม่ครบสักทีจนเกินเพดานเวลา
        # ไม่ใช่ค้างอยู่ในโหมดถ่ายจนกว่าจะมีคนมากดยกเลิก
        gone = now - job.last_face_at > ENROLL_NO_FACE_S
        too_long = now - job.started_at > ENROLL_TIMEOUT_S
        if gone or too_long:
            reason = "no_face" if gone else "timeout"
            log.info("เลิกเก็บตัวอย่างใบหน้า (%s) ได้ %d/%d ใบ",
                     reason, len(job.samples), ENROLL_SAMPLES)
            with self._lock:
                self._mode = "idle"
                self._enroll = None
            self._emit("enroll", {"state": "failed", "reason": reason,
                                  "progress": self._enroll_progress(job)})
            return

        if len(usable) > 1:
            if now - job.last_hint_at > ENROLL_HINT_EVERY_S:
                job.last_hint_at = now
                self._emit("enroll", {"state": "multi"})
            return
        if not usable:
            # ไม่ส่งทุกเฟรม เพราะเฟรมเข้ามาหลายสิบครั้งต่อวินาที
            if now - job.last_hint_at > ENROLL_HINT_EVERY_S:
                job.last_hint_at = now
                self._emit("enroll", {"state": "searching",
                                      "progress": self._enroll_progress(job)})
            time.sleep(0.05)
            return

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
