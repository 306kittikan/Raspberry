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
import os
import threading
import time
from typing import Any

import numpy as np

from .. import config

log = logging.getLogger("kiosk.stt")

SAMPLE_RATE = 16_000

# คำเฉพาะของสาขาที่ตัวถอดความไม่เคยเห็นมาก่อน
#
# โมเดลถอดเสียงถูกฝึกจากภาษาไทยทั่วไป จึงไม่รู้จักชื่ออาจารย์ ชื่ออาคาร
# หรือศัพท์เฉพาะของที่นี่ แล้วจะเดาเป็นคำที่เสียงใกล้กันแต่คนละความหมาย
# เช่น "สหกิจศึกษา" กลายเป็น "สหกิจ ศึกษา" หรือ "แม่โจ้" กลายเป็น "แม่โจ"
#
# การใส่คำเหล่านี้เป็นบริบทตั้งต้นช่วยให้โมเดลเอนไปทางคำที่ถูกต้อง
# เป็นวิธีมาตรฐานของ Whisper ที่ไม่ต้องฝึกโมเดลใหม่และไม่เสียความเร็ว
VOCABULARY = (
    "มหาวิทยาลัยแม่โจ้ คณะวิทยาศาสตร์ สาขาวิชาวิทยาการคอมพิวเตอร์ "
    "ตารางเรียน ตารางสอบ กำหนดสอบ สอบกลางภาค สอบปลายภาค "
    "ลงทะเบียนเรียน เพิ่มถอนรายวิชา สหกิจศึกษา ฝึกงาน หน่วยกิต "
    "อาจารย์ที่ปรึกษา สำนักงานสาขา อาคารจุฬาภรณ์ ตึก 60 ปี "
    "ห้องปฏิบัติการคอมพิวเตอร์ ปัญญาประดิษฐ์ ฐานข้อมูล เครือข่าย"
)

# ความกว้างของการค้นหาคำตอบ ยิ่งกว้างยิ่งแม่นแต่ช้าลง
# 1 = เร็วที่สุด · 5 = แม่นที่สุด
# บน Raspberry Pi 5 ค่า 3 ยังอยู่ในเกณฑ์ที่ผู้ใช้ยืนรอไหว
BEAM_SIZE = int(os.getenv("KIOSK_STT_BEAM", "3"))
# เว้นช่วงก่อนลองโหลดโมเดลใหม่หลังล้มเหลว
# การโหลดใช้เวลาหลายวินาทีและกินหน่วยความจำมาก ลองถี่เกินไปจะยิ่งทำให้แย่ลง
RELOAD_COOLDOWN_S = 30.0
# เสียงที่สั้นกว่านี้ไม่น่าจะเป็นคำถาม มักเป็นเสียงกระแทกหรือแตะจอ
MIN_AUDIO_SECONDS = 0.4
MAX_AUDIO_SECONDS = 15.0


class SpeechEngine:
    def __init__(self) -> None:
        self._model: Any = None
        self._lock = threading.Lock()
        self._load_lock = threading.Lock()
        self._error: str | None = None
        self._last_try_at = 0.0

    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def error(self) -> str | None:
        return self._error

    def ensure_ready(self) -> bool:
        """พร้อมใช้งานหรือยัง ถ้ายังให้ลองโหลดใหม่เป็นระยะ

        โมเดลอาจโหลดไม่ผ่านตอนเปิดเครื่องเพราะหน่วยความจำยังไม่ว่างพอ
        ถ้าไม่ลองใหม่เลย ช่องทางเสียงจะตายไปทั้งวันจนกว่าจะมีคนเริ่มบริการใหม่
        ทั้งที่ปัญหาหายไปเองภายในไม่กี่นาที
        """
        if self._model is not None:
            return True
        if time.monotonic() - self._last_try_at < RELOAD_COOLDOWN_S:
            return False
        # มีคนกำลังโหลดอยู่แล้ว ไม่ต้องโหลดซ้อน เพราะกินหน่วยความจำสองเท่า
        if not self._load_lock.acquire(blocking=False):
            return False
        try:
            return self.load()
        finally:
            self._load_lock.release()

    def load(self) -> bool:
        if self._model is not None:
            return True
        self._last_try_at = time.monotonic()
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
                beam_size=BEAM_SIZE,
                initial_prompt=VOCABULARY,   # บอกคำเฉพาะของสาขาไว้ก่อน
                vad_filter=True,        # ตัดช่วงเงียบออกก่อน ลดเวลาประมวลผล
                vad_parameters={"min_silence_duration_ms": 350},
                condition_on_previous_text=False,  # แต่ละคำถามเป็นอิสระจากกัน
                # ถ้าโมเดลไม่มั่นใจเลย ปล่อยให้คืนค่าว่างดีกว่าเดาเป็นคำมั่ว
                # ข้อความที่ถอดผิดจะถูกส่งต่อไปตีความ แล้วได้คำตอบที่ผิดเรื่องไปทั้งสาย
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
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
