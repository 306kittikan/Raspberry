"""แปลงเสียงพูดภาษาไทยเป็นข้อความ

ใช้ faster-whisper ซึ่งทำงานได้โดยไม่ต้องต่ออินเทอร์เน็ต
เหตุผลที่ไม่ใช้ Web Speech API ของเบราว์เซอร์: Chromium บน Raspberry Pi
ไม่มีบริการรู้จำเสียงให้ใช้ (ต่างจาก Chrome บน Windows/macOS)
ถ้าพึ่งมันแล้วย้ายไปลงตู้จริง ฟีเจอร์เสียงจะใช้ไม่ได้ทันที

เสียงถูกอัดจากไมโครโฟนที่เบราว์เซอร์ด้วย MediaRecorder (รูปแบบ webm/opus)
แล้วส่งมาเป็นก้อนเดียวทาง WebSocket ฝั่งเซิร์ฟเวอร์ถอดรหัสด้วย PyAV
ซึ่งติดมากับ faster-whisper อยู่แล้ว จึงไม่ต้องลง ffmpeg เพิ่ม
และฝั่งเบราว์เซอร์ไม่ต้องเขียน AudioWorklet แปลงสัญญาณเอง

ประมวลผลที่เซิร์ฟเวอร์ และ **ไม่มีการบันทึกไฟล์เสียงลงดิสก์**
ข้อมูลเสียงอยู่ในหน่วยความจำจนกว่าจะถอดความเสร็จแล้วถูกทิ้งทันที

ข้อควรรู้เรื่องความเร็ว
  รุ่น base บนโน้ตบุ๊กถอดความประโยคสั้นได้ในราว 0.5–1.5 วินาที
  บน Raspberry Pi 5 ราว 2–5 วินาที ซึ่งยอมรับได้สำหรับช่องทางเสริม
  ถ้าต้องการความแม่นกว่านี้ให้เปลี่ยนเป็นรุ่น small แลกกับเวลาที่นานขึ้น
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np

from .. import config

log = logging.getLogger("kiosk.stt")

SAMPLE_RATE = 16_000
# เสียงที่สั้นกว่านี้ไม่น่าจะเป็นคำถาม มักเป็นเสียงกระแทกหรือแตะจอ
MIN_AUDIO_SECONDS = 0.4
MAX_AUDIO_SECONDS = 15.0


class SpeechEngine:
    def __init__(self) -> None:
        self._model: Any = None
        self._lock = threading.Lock()
        self._error: str | None = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def error(self) -> str | None:
        return self._error

    def load(self) -> bool:
        if self._model is not None:
            return True
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                config.STT_MODEL,
                device="cpu",
                # int8 เร็วกว่า float32 หลายเท่าบนซีพียู และคุณภาพต่างกันน้อยมาก
                compute_type="int8",
                download_root=str(config.STT_MODEL_DIR),
                local_files_only=config.STT_OFFLINE_ONLY,
            )
            self._error = None
            log.info("โหลดโมเดลถอดความเสียง %s เรียบร้อย", config.STT_MODEL)
            return True
        except Exception as exc:  # noqa: BLE001 — ไม่มีโมเดลต้องไม่ทำให้ตู้ล่ม
            self._error = str(exc)
            log.warning("โหลดโมเดลถอดความเสียงไม่ได้: %s", exc)
            return False

    def transcribe(self, audio: np.ndarray) -> dict[str, Any]:
        """audio เป็น float32 ช่วง -1..1 อัตราสุ่ม 16 kHz"""
        if self._model is None:
            return {"text": "", "ok": False, "reason": "model_not_ready"}

        seconds = len(audio) / SAMPLE_RATE
        if seconds < MIN_AUDIO_SECONDS:
            return {"text": "", "ok": False, "reason": "too_short", "seconds": round(seconds, 2)}
        if seconds > MAX_AUDIO_SECONDS:
            audio = audio[: int(MAX_AUDIO_SECONDS * SAMPLE_RATE)]
            seconds = MAX_AUDIO_SECONDS

        with self._lock:  # โมเดลเดียวใช้ข้ามเธรดพร้อมกันไม่ได้
            segments, info = self._model.transcribe(
                audio,
                language="th",          # บังคับภาษาไทย ไม่ให้เดาเป็นภาษาอื่น
                beam_size=1,            # เร็วกว่า beam กว้าง และคำถามสั้น ๆ ไม่ต่างกันมาก
                vad_filter=True,        # ตัดช่วงเงียบออกก่อน ลดเวลาประมวลผล
                vad_parameters={"min_silence_duration_ms": 350},
                condition_on_previous_text=False,  # แต่ละคำถามเป็นอิสระจากกัน
            )
            parts = [s.text for s in segments]

        text = "".join(parts).strip()
        return {
            "text": text,
            "ok": bool(text),
            "reason": "empty" if not text else None,
            "seconds": round(seconds, 2),
            "probability": round(float(getattr(info, "language_probability", 0.0)), 3),
        }


engine = SpeechEngine()


def decode(data: bytes) -> np.ndarray:
    """ถอดรหัสเสียงที่เบราว์เซอร์อัดมา (webm/opus, ogg, wav ก็ได้) เป็น float32 16 kHz"""
    import io

    from faster_whisper.audio import decode_audio

    return decode_audio(io.BytesIO(data), sampling_rate=SAMPLE_RATE)
