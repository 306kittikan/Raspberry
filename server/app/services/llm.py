"""เรียกโมเดลภาษาให้สรุปคำตอบจากเอกสารที่ค้นมาให้แล้ว

แยกออกมาจาก assistant_ai.py ด้วยเหตุผลเดียว คือด่านกันการแต่งคำตอบ
(ตรวจว่าหมายเลขชิ้นเอกสารอยู่ในบริบทจริง แล้วดึงป้ายอ้างอิงจากฐานข้อมูลเอง)
ต้องทำงานเหมือนกันทุกประการไม่ว่าจะใช้ผู้ให้บริการรายใด
การเปลี่ยนผู้ให้บริการจึงต้องไม่แตะด่านเหล่านั้นแม้แต่บรรทัดเดียว

รองรับสองราย เลือกด้วย KIOSK_AI_PROVIDER หรือปล่อยให้เดาจากกุญแจที่ใส่ไว้
  gemini     — มีโควตาให้ใช้ฟรี เหมาะกับงานที่งบจำกัด
  anthropic  — เสียเงินตามการใช้งาน

ทั้งสองรายถูกบังคับให้ตอบกลับเป็นโครงสร้างที่กำหนดไว้ (JSON ตามสคีมา)
ไม่ใช่ข้อความอิสระที่ต้องมาแกะเอง เพราะการแกะข้อความอิสระพังเงียบ ๆ ได้ง่าย
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .. import config

log = logging.getLogger("kiosk.ai")

_client: Any = None
_client_provider: str | None = None


@dataclass(slots=True)
class Completion:
    """ผลที่ได้จากโมเดล แปลงเป็นรูปเดียวกันแล้วไม่ว่ามาจากผู้ให้บริการใด"""

    parsed: Any | None
    input_tokens: int = 0
    output_tokens: int = 0
    refused: bool = False   # โมเดลปฏิเสธที่จะตอบเอง ไม่ใช่ตอบว่าไม่รู้


class LlmError(Exception):
    """เรียกโมเดลไม่สำเร็จ พร้อมรหัสสาเหตุสำหรับบันทึกและแสดงให้เจ้าหน้าที่

    รหัสสาเหตุต้องเหมือนกันข้ามผู้ให้บริการ เพราะเจ้าหน้าที่ที่ดูแลตู้
    สนใจว่า "กุญแจมีปัญหา" หรือ "เน็ตมีปัญหา" ไม่ได้สนใจว่าใครเป็นคนบอก
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def provider() -> str:
    """ผู้ให้บริการที่จะใช้จริง — 'gemini' | 'anthropic' | 'none'"""
    choice = config.AI_PROVIDER
    if choice == "gemini":
        return "gemini" if config.GEMINI_API_KEY else "none"
    if choice == "anthropic":
        return "anthropic" if config.ANTHROPIC_API_KEY else "none"

    # อัตโนมัติ: ใช้กุญแจที่ใส่ไว้ ถ้ามีทั้งคู่ให้ gemini ก่อนเพราะมีโควตาฟรี
    if config.GEMINI_API_KEY:
        return "gemini"
    if config.ANTHROPIC_API_KEY:
        return "anthropic"
    return "none"


def model_name() -> str:
    return {
        "gemini": config.GEMINI_MODEL,
        "anthropic": config.ANTHROPIC_MODEL,
    }.get(provider(), "-")


def reset() -> None:
    """ทิ้งตัวเชื่อมต่อเดิม ใช้ตอนเปลี่ยนการตั้งค่าระหว่างทดสอบ"""
    global _client, _client_provider
    _client = None
    _client_provider = None


# ------------------------------------------------------------
async def complete(*, system: str, prompt: str, schema: type[BaseModel]) -> Completion:
    """ส่งคำถามพร้อมเอกสารให้โมเดล แล้วคืนคำตอบตามสคีมาที่กำหนด

    โยน LlmError เมื่อเรียกไม่สำเร็จ ไม่กลืนข้อผิดพลาดเงียบ ๆ
    เพราะผู้เรียกต้องรู้สาเหตุเพื่อเอาไปบันทึกและแสดงข้อความที่ถูกต้อง
    """
    name = provider()
    if name == "gemini":
        return await _gemini(system, prompt, schema)
    if name == "anthropic":
        return await _anthropic(system, prompt, schema)
    raise LlmError("no_key", "ยังไม่ได้ตั้งค่ากุญแจของผู้ช่วย AI")


# ------------------------------------------------------------
def _gemini_client():
    global _client, _client_provider
    if _client is None or _client_provider != "gemini":
        from google import genai
        from google.genai import types

        _client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                # ฝั่งนี้คิดเป็นมิลลิวินาที ต่างจากฝั่ง anthropic ที่คิดเป็นวินาที
                timeout=int(config.AI_TIMEOUT_SECONDS * 1000),
                # attempts นับรวมครั้งแรกด้วย ส่วน max_retries ของ anthropic นับเฉพาะครั้งที่ลองซ้ำ
                # จึงต้องบวกหนึ่ง เพื่อให้ KIOSK_AI_RETRIES มีความหมายเดียวกันทั้งสองฝั่ง
                retry_options=types.HttpRetryOptions(
                    attempts=config.AI_MAX_RETRIES + 1,
                    initial_delay=0.5,
                    max_delay=4.0,
                ),
            ),
        )
        _client_provider = "gemini"
    return _client


async def _gemini(system: str, prompt: str, schema: type[BaseModel]) -> Completion:
    from google.genai import errors, types

    try:
        response = await _gemini_client().aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                max_output_tokens=config.AI_MAX_TOKENS,
                # ปิดการคิดก่อนตอบ คำตอบมาจากเอกสารที่ค้นมาให้แล้ว
                # ไม่ต้องคิดหลายชั้น และการคิดกินทั้งเวลาและโควตา
                thinking_config=types.ThinkingConfig(thinking_budget=config.AI_THINKING_BUDGET),
            ),
        )
    except errors.ClientError as exc:
        code = getattr(exc, "code", None)
        if code == 429:
            raise LlmError("rate_limit", "โควตาการใช้งานเต็ม") from exc
        if code in (401, 403):
            raise LlmError("auth", "กุญแจไม่ถูกต้องหรือหมดสิทธิ์") from exc
        raise LlmError(f"http_{code}", str(exc)[:120]) from exc
    except errors.ServerError as exc:
        # โควตาฟรีเจอ 503 ได้บ่อยเวลามีผู้ใช้พร้อมกันมาก
        raise LlmError("unavailable", "ผู้ให้บริการไม่พร้อมรับคำขอ") from exc
    except errors.APIError as exc:
        raise LlmError("api_error", str(exc)[:120]) from exc
    except Exception as exc:  # noqa: BLE001 — เครือข่ายล้มต้องไม่ทำให้ตู้ล่ม
        raise LlmError("connection", str(exc)[:120]) from exc

    usage = getattr(response, "usage_metadata", None)

    # โมเดลอาจหยุดกลางคันเพราะตัวกรองความปลอดภัยหรือชนเพดานโทเค็น
    finish = None
    if response.candidates:
        finish = str(getattr(response.candidates[0], "finish_reason", "") or "")
    refused = "SAFETY" in finish.upper() if finish else False

    return Completion(
        parsed=response.parsed,
        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
        output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        refused=refused,
    )


# ------------------------------------------------------------
def _anthropic_client():
    global _client, _client_provider
    if _client is None or _client_provider != "anthropic":
        from anthropic import AsyncAnthropic

        # จำกัดการลองใหม่ไว้เอง ไลบรารีตั้งไว้ 2 ครั้งซึ่งเหมาะกับงานเบื้องหลัง
        # แต่ที่นี่มีคนยืนรออยู่หน้าจอ เวลารวมที่แย่ที่สุดต้องคาดเดาได้
        _client = AsyncAnthropic(
            api_key=config.ANTHROPIC_API_KEY or None,
            timeout=config.AI_TIMEOUT_SECONDS,
            max_retries=config.AI_MAX_RETRIES,
        )
        _client_provider = "anthropic"
    return _client


async def _anthropic(system: str, prompt: str, schema: type[BaseModel]) -> Completion:
    import anthropic

    try:
        response = await _anthropic_client().messages.parse(
            model=config.ANTHROPIC_MODEL,
            # โทเค็นที่ใช้คิดนับรวมในเพดานนี้ด้วย ตั้งต่ำไปคำตอบจะถูกตัดกลางคัน
            max_tokens=config.AI_MAX_TOKENS,
            output_config={"effort": config.AI_EFFORT},
            system=system,
            output_format=schema,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.RateLimitError as exc:
        raise LlmError("rate_limit", "โควตาการใช้งานเต็ม") from exc
    except anthropic.AuthenticationError as exc:
        raise LlmError("auth", "กุญแจไม่ถูกต้องหรือหมดอายุ") from exc
    except anthropic.APIConnectionError as exc:
        raise LlmError("connection", "เชื่อมต่อไม่ได้") from exc
    except anthropic.APIStatusError as exc:
        code = "unavailable" if exc.status_code >= 500 else f"http_{exc.status_code}"
        raise LlmError(code, str(exc)[:120]) from exc
    except Exception as exc:  # noqa: BLE001
        raise LlmError("api_error", str(exc)[:120]) from exc

    usage = getattr(response, "usage", None)
    return Completion(
        parsed=response.parsed_output,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        refused=getattr(response, "stop_reason", None) == "refusal",
    )
