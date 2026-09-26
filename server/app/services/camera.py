"""แหล่งภาพจากกล้อง

กล้องเป็นของเซิร์ฟเวอร์ ไม่ใช่ของเบราว์เซอร์ เพราะ
  1. การรู้จำใบหน้าทำงานอยู่ฝั่ง Python อยู่แล้ว ส่งเฟรมจากเบราว์เซอร์มาถือว่าเสียเปล่า
  2. Chromium โหมด kiosk บน Raspberry Pi ขออนุญาตใช้กล้องยุ่งยาก
  3. บน Pi ที่ใช้ Pi Camera Module ต้องใช้ picamera2 ซึ่งเบราว์เซอร์เข้าไม่ถึง

หน้าเว็บดูภาพสดผ่านสตรีม MJPEG ที่ /api/camera/stream แทน

รองรับสามแบบ เลือกด้วย KIOSK_CAMERA
  auto        ลอง picamera2 ก่อน ถ้าไม่มีใช้กล้อง USB ตัวแรก
  picamera    บังคับใช้ Pi Camera Module
  0, 1, 2...  เลขอุปกรณ์กล้อง USB
  off         ปิดกล้อง (ระบบจะสลับไปใช้การกรอกรหัสนักศึกษา)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np

from .. import config

log = logging.getLogger("kiosk.camera")

FRAME_WIDTH = 640
FRAME_HEIGHT = 480


class CameraError(RuntimeError):
    """เปิดกล้องไม่ได้ — ระบบต้องสลับไปใช้การกรอกรหัสนักศึกษาแทน"""


class _Backend:
    def read(self) -> np.ndarray | None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class _OpenCVBackend(_Backend):
    """กล้อง USB ผ่าน OpenCV — ใช้ได้ทั้งบน Windows และ Raspberry Pi"""

    def __init__(self, index: int) -> None:
        import cv2

        self._cv2 = cv2
        # บน Windows ต้องระบุ DSHOW ไม่งั้นเปิดกล้องช้ามากและบางตัวเปิดไม่ติด
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if hasattr(cv2, "CAP_DSHOW") else [cv2.CAP_ANY]
        cap = None
        for backend in backends:
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                break
            cap.release()
            cap = None
        if cap is None:
            raise CameraError(f"เปิดกล้องหมายเลข {index} ไม่ได้")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # อ่านเฟรมล่าสุดเสมอ ไม่ใช่เฟรมค้างในคิว
        self._cap = cap
        for _ in range(5):  # ให้กล้องปรับแสงก่อนใช้งานจริง
            cap.read()

    def read(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        self._cap.release()


class _PiCameraBackend(_Backend):
    """Pi Camera Module ผ่าน picamera2 (มีเฉพาะบน Raspberry Pi OS)"""

    def __init__(self) -> None:
        from picamera2 import Picamera2

        self._cam = Picamera2()
        cfg = self._cam.create_preview_configuration(
            main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
        )
        self._cam.configure(cfg)
        self._cam.start()
        time.sleep(0.6)  # รอให้ปรับแสงอัตโนมัติเสร็จ

    def read(self) -> np.ndarray | None:
        frame = self._cam.capture_array()
        # picamera2 คืน RGB ส่วนโค้ดที่เหลือทำงานบน BGR ตามแบบ OpenCV
        return frame[:, :, ::-1].copy()

    def close(self) -> None:
        self._cam.stop()
        self._cam.close()


def _open_backend(source: str) -> _Backend:
    if source == "picamera":
        return _PiCameraBackend()
    if source.isdigit():
        return _OpenCVBackend(int(source))
    if source == "auto":
        try:
            return _PiCameraBackend()
        except Exception:  # noqa: BLE001 — ไม่มี picamera2 เป็นเรื่องปกติบนเครื่องพัฒนา
            return _OpenCVBackend(0)
    raise CameraError(f"ไม่รู้จักค่ากล้อง '{source}'")


class Camera:
    """อ่านเฟรมต่อเนื่องในเธรดเดียว แล้วแจกเฟรมล่าสุดให้ผู้ใช้ทุกคน

    ทั้งตัวรู้จำใบหน้าและสตรีมภาพบนหน้าจอต้องการเฟรมพร้อมกัน
    ถ้าต่างคนต่างอ่านจากอุปกรณ์จะแย่งกันจนภาพกระตุก จึงอ่านที่เดียวแล้วแบ่งกันใช้
    """

    def __init__(self) -> None:
        self._backend: _Backend | None = None
        self._frame: np.ndarray | None = None
        self._frame_at: float = 0.0
        self._seq = 0
        self._lock = threading.Lock()
        self._new_frame = threading.Condition(self._lock)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._error: str | None = None

    # ---- วงจรชีวิต ----
    @property
    def enabled(self) -> bool:
        return config.CAMERA_SOURCE.strip().lower() != "off"

    @property
    def available(self) -> bool:
        return self._backend is not None and self._error is None

    @property
    def error(self) -> str | None:
        return self._error

    def start(self) -> bool:
        if not self.enabled:
            self._error = "ปิดการใช้งานกล้องไว้ในการตั้งค่า"
            log.info("กล้อง: %s", self._error)
            return False
        if self._thread is not None:
            return self.available

        try:
            self._backend = _open_backend(config.CAMERA_SOURCE.strip().lower())
        except Exception as exc:  # noqa: BLE001 — กล้องเสียต้องไม่ทำให้ตู้ทั้งตู้ล่ม
            self._error = str(exc)
            log.warning("เปิดกล้องไม่ได้: %s", exc)
            return False

        self._error = None
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="camera", daemon=True)
        self._thread.start()
        log.info("กล้องพร้อมใช้งาน (source=%s)", config.CAMERA_SOURCE)
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._backend is not None:
            try:
                self._backend.close()
            except Exception:  # noqa: BLE001
                pass
            self._backend = None

    def _loop(self) -> None:
        misses = 0
        while not self._stop.is_set():
            frame = None
            try:
                frame = self._backend.read() if self._backend else None
            except Exception as exc:  # noqa: BLE001
                log.warning("อ่านเฟรมไม่สำเร็จ: %s", exc)

            if frame is None:
                misses += 1
                # กล้องถูกถอดสายหรือค้าง — ถือว่าใช้งานไม่ได้แล้ว
                if misses >= 30:
                    self._error = "กล้องหยุดส่งภาพ"
                    log.warning("กล้องหยุดส่งภาพ หยุดอ่านเฟรม")
                    break
                time.sleep(0.05)
                continue

            misses = 0
            with self._new_frame:
                self._frame = frame
                self._frame_at = time.time()
                self._seq += 1
                self._new_frame.notify_all()
            time.sleep(0.01)

    # ---- อ่านเฟรม ----
    def latest(self) -> tuple[np.ndarray | None, int]:
        with self._lock:
            if self._frame is None:
                return None, self._seq
            return self._frame.copy(), self._seq

    def wait_for_frame(self, after_seq: int, timeout: float = 2.0) -> tuple[np.ndarray | None, int]:
        """รอเฟรมใหม่กว่าที่เคยเห็น ใช้กับสตรีมภาพเพื่อไม่ให้ส่งเฟรมซ้ำ"""
        with self._new_frame:
            if self._seq <= after_seq:
                self._new_frame.wait(timeout)
            if self._frame is None or self._seq <= after_seq:
                return None, self._seq
            return self._frame.copy(), self._seq

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.available,
            "error": self._error,
            "source": config.CAMERA_SOURCE,
            "lastFrameAgo": round(time.time() - self._frame_at, 2) if self._frame_at else None,
        }


camera = Camera()
