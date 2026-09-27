"""ตรวจด่านกันการแต่งคำตอบของผู้ช่วย AI

    .venv/Scripts/python.exe scripts/test_assistant_ai.py

ไม่ต้องใช้กุญแจ API และไม่เรียกโมเดลจริง จึงไม่มีค่าใช้จ่ายและรันซ้ำได้เสมอ
วิธีทดสอบคือสวมโมเดลปลอมที่ "จงใจตอบผิด" แบบที่โมเดลจริงอาจตอบ
แล้วดูว่าเซิร์ฟเวอร์กรองออกได้หรือไม่

ทำไมต้องมีชุดทดสอบนี้
  ด่านเหล่านี้คือสิ่งเดียวที่กันไม่ให้คำตอบที่แต่งขึ้นขึ้นไปอยู่บนจอ
  นักศึกษาที่เชื่อคำตอบผิดอาจเดินไปผิดตึกหรือพลาดกำหนดส่งเอกสาร
  และความผิดพลาดแบบนี้จะไม่มีใครสังเกตเห็นจนกว่าจะสายเกินไป
  ถ้าไม่ทดสอบ เราจะรู้ว่าด่านพังก็ต่อเมื่อมีคนได้รับคำตอบผิดไปแล้ว
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db as db_module  # noqa: E402
from app.services import assistant_ai, retrieval  # noqa: E402

_results: list[tuple[bool, str]] = []


def check(ok: bool, name: str, expected: str = "", actual: str = "") -> bool:
    _results.append((ok, name))
    print(f"  [{'ผ่าน' if ok else 'ไม่ผ่าน'}] {name}")
    if not ok:
        print(f"         ควรได้  : {expected}")
        print(f"         ได้จริง : {actual}")
    return ok


# ------------------------------------------------------------
# โมเดลปลอม
# ------------------------------------------------------------
class FakeUsage:
    input_tokens = 1200
    output_tokens = 80


class FakeResponse:
    def __init__(self, parsed: Any, stop_reason: str = "end_turn") -> None:
        self.parsed_output = parsed
        self.stop_reason = stop_reason
        self.usage = FakeUsage()


class FakeMessages:
    """รับคำขอแล้วคืนสิ่งที่ตั้งไว้ล่วงหน้า หรือโยนข้อผิดพลาดที่ตั้งไว้"""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.last_request: dict[str, Any] | None = None

    async def parse(self, **kwargs: Any) -> FakeResponse:
        self.last_request = kwargs
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome: Any) -> None:
        self.messages = FakeMessages(outcome)


def with_fake(outcome: Any) -> FakeClient:
    """สวมโมเดลปลอมเข้าไปแทนของจริง"""
    client = FakeClient(outcome)
    assistant_ai._get_client = lambda: client   # noqa: SLF001
    assistant_ai.health.__init__()              # ล้างตัวนับก่อนทุกกรณี
    config.AI_ENABLED = True                    # ข้ามการตรวจกุญแจ
    return client


def ask(conn, question: str) -> dict[str, Any]:
    return asyncio.run(assistant_ai.answer_open(conn, question))


def answer(found: bool = True, chunk_id: int | None = None,
           lines: list[str] | None = None) -> assistant_ai.AiAnswer:
    return assistant_ai.AiAnswer(
        found=found,
        chunk_id=chunk_id,
        lines=lines if lines is not None else ["บรรทัดตอบทดสอบ"],
    )


# ------------------------------------------------------------
def main() -> int:
    conn = db_module.connect()
    real_enabled = config.AI_ENABLED
    real_client = assistant_ai._get_client   # noqa: SLF001

    # คำถามที่ค้นเอกสารเจอแน่ ๆ ใช้เป็นฐานของทุกกรณี
    question = "ติดต่อสาขาได้ทางไหน"
    hits = retrieval.search(conn, question, limit=config.AI_CONTEXT_CHUNKS)
    if not hits:
        print("ค้นเอกสารไม่เจอ — นำเข้าเอกสารของสาขาก่อนแล้วรันใหม่")
        return 2
    good_id = hits[0]["chunkId"]

    try:
        print("\n1. คำตอบที่ถูกต้อง")
        fake = with_fake(FakeResponse(answer(chunk_id=good_id, lines=["ติดต่อได้ที่ cs@mju.ac.th"])))
        result = ask(conn, question)
        check(result["source"] == "ai", "คำตอบที่อ้างอิงถูกต้องผ่านได้", "source=ai", str(result["source"]))
        check(result.get("ref") == retrieval.citation_for_chunk(conn, good_id),
              "ป้ายอ้างอิงมาจากฐานข้อมูล ไม่ใช่จากสิ่งที่โมเดลพิมพ์",
              str(retrieval.citation_for_chunk(conn, good_id)), str(result.get("ref")))
        check(assistant_ai.health.last_ok_at is not None,
              "บันทึกเวลาที่เรียกสำเร็จไว้", "มีเวลา", str(assistant_ai.health.last_ok_at))
        check(assistant_ai.health.input_tokens == 1200,
              "นับโทเค็นที่ใช้ไปเพื่อประเมินค่าใช้จ่าย", "1200",
              str(assistant_ai.health.input_tokens))

        print("\n2. พารามิเตอร์ที่ส่งให้โมเดล")
        sent = fake.messages.last_request or {}
        check(sent.get("model") == config.ANTHROPIC_MODEL,
              "ใช้รุ่นโมเดลตามที่ตั้งค่าไว้", config.ANTHROPIC_MODEL, str(sent.get("model")))
        check(sent.get("max_tokens", 0) >= 4000,
              "เพดานโทเค็นสูงพอ เพราะโทเค็นที่ใช้คิดนับรวมอยู่ด้วย",
              ">= 4000", str(sent.get("max_tokens")))
        check(sent.get("output_format") is assistant_ai.AiAnswer,
              "บังคับรูปแบบคำตอบด้วยโครงสร้างที่กำหนดไว้",
              "AiAnswer", str(sent.get("output_format")))
        context = str(sent.get("messages"))
        check("chunk_id=" in context,
              "ส่งหมายเลขชิ้นเอกสารไปให้โมเดลเลือก", "มี chunk_id=", context[:60])

        print("\n3. โมเดลแต่งหมายเลขเอกสารขึ้นเอง")
        with_fake(FakeResponse(answer(chunk_id=999_999, lines=["คำตอบที่ไม่มีที่มา"])))
        result = ask(conn, question)
        check(result["source"] == "none",
              "หมายเลขที่ไม่ได้อยู่ในบริบทถูกปฏิเสธ", "source=none", str(result["source"]))
        check("คำตอบที่ไม่มีที่มา" not in str(result["lines"]),
              "เนื้อหาที่แต่งขึ้นไม่หลุดออกไปบนหน้าจอ", "ไม่มีข้อความนั้น", str(result["lines"])[:60])

        print("\n4. โมเดลอ้างเอกสารจริง แต่ไม่ใช่ชิ้นที่ส่งไปให้")
        other = conn.execute(
            "SELECT id FROM doc_chunks WHERE id NOT IN ({}) LIMIT 1".format(
                ",".join(str(h["chunkId"]) for h in hits)
            )
        ).fetchone()
        with_fake(FakeResponse(answer(chunk_id=other["id"], lines=["อ้างเอกสารที่ไม่ได้อ่าน"])))
        result = ask(conn, question)
        check(result["source"] == "none",
              "ชิ้นเอกสารที่ไม่ได้ส่งไปให้อ่านก็ถูกปฏิเสธเช่นกัน",
              "source=none", str(result["source"]))

        print("\n5. โมเดลบอกเองว่าไม่พบคำตอบ")
        with_fake(FakeResponse(answer(found=False, chunk_id=good_id, lines=["เดาไปก่อน"])))
        result = ask(conn, question)
        check(result["source"] == "none", "ยอมรับคำว่าไม่รู้ ไม่ฝืนแสดงคำตอบ",
              "source=none", str(result["source"]))

        print("\n6. โมเดลตอบว่าพบ แต่ไม่มีเนื้อหา")
        with_fake(FakeResponse(answer(chunk_id=good_id, lines=[])))
        result = ask(conn, question)
        check(result["source"] == "none", "คำตอบว่างเปล่าถูกปฏิเสธ ไม่ขึ้นจอเปล่า",
              "source=none", str(result["source"]))

        print("\n7. โมเดลปฏิเสธคำถามเอง")
        with_fake(FakeResponse(answer(chunk_id=good_id), stop_reason="refusal"))
        result = ask(conn, question)
        check(result["source"] == "none", "คำถามที่โมเดลปฏิเสธไม่ถูกนำไปแสดง",
              "source=none", str(result["source"]))
        check(assistant_ai.health.last_error == "refusal",
              "บันทึกสาเหตุไว้ว่าเป็นการปฏิเสธ", "refusal",
              str(assistant_ai.health.last_error))

        print("\n8. เรียก API ไม่สำเร็จ")
        import anthropic
        import httpx2

        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        cases = [
            (anthropic.APIConnectionError(request=request), "connection", "เน็ตหลุด"),
            (
                anthropic.RateLimitError(
                    "ถูกจำกัดอัตรา",
                    response=httpx2.Response(429, request=request),
                    body=None,
                ),
                "rate_limit",
                "ผู้ใช้หนาแน่น",
            ),
            (
                anthropic.AuthenticationError(
                    "กุญแจไม่ถูกต้อง",
                    response=httpx2.Response(401, request=request),
                    body=None,
                ),
                "auth",
                "กุญแจหมดอายุ",
            ),
        ]
        for exc, code, label in cases:
            with_fake(exc)
            result = ask(conn, question)
            ok = result["source"] == "none" and assistant_ai.health.last_error == code
            check(ok, f"{label} → ตอบว่าไม่พบข้อมูล พร้อมบันทึกสาเหตุ '{code}'",
                  f"source=none, lastError={code}",
                  f"source={result['source']}, lastError={assistant_ai.health.last_error}")

        print("\n9. ข้อผิดพลาดที่ไม่ได้คาดไว้ต้องไม่ทำให้ตู้ล่ม")
        with_fake(RuntimeError("อะไรสักอย่างที่ไม่เคยเจอ"))
        result = ask(conn, question)
        check(result["source"] == "none", "จับได้ทุกกรณี ตู้ยังตอบต่อได้",
              "source=none", str(result["source"]))

        print("\n10. ค้นเอกสารไม่เจอ ต้องไม่เรียกโมเดลเลย")
        fake = with_fake(FakeResponse(answer(chunk_id=good_id)))
        result = ask(conn, "ราคาทองคำวันนี้เท่าไร")
        check(result["source"] == "none", "คำถามนอกเรื่องตอบว่าไม่พบข้อมูล",
              "source=none", str(result["source"]))
        check(fake.messages.last_request is None,
              "ไม่เสียค่าเรียกโมเดลกับคำถามที่ไม่มีเอกสารรองรับ",
              "ไม่เรียกโมเดล", "เรียกไปแล้ว")

        print("\n11. ปิดผู้ช่วย AI ไว้")
        fake = with_fake(FakeResponse(answer(chunk_id=good_id)))
        config.AI_ENABLED = False
        result = ask(conn, question)
        check(result["source"] == "none" and fake.messages.last_request is None,
              "เมื่อปิดไว้ ต้องไม่เรียกโมเดลและไม่เดาคำตอบ",
              "ไม่เรียกโมเดล", str(fake.messages.last_request is not None))

        print("\n12. ทุกคำตอบที่ปฏิเสธต้องมีช่องทางติดต่อ")
        config.AI_ENABLED = True
        with_fake(FakeResponse(answer(chunk_id=999_999)))
        result = ask(conn, question)
        text = " ".join(result["lines"])
        check("@" in text or "โทร" in text or "สำนักงาน" in text,
              "บอกช่องทางติดต่อสาขาแทน ไม่ใช่ปล่อยให้ผู้ใช้ค้าง",
              "มีช่องทางติดต่อ", text[:70])

    finally:
        assistant_ai._get_client = real_client   # noqa: SLF001
        config.AI_ENABLED = real_enabled
        conn.close()

    passed = sum(1 for ok, _ in _results if ok)
    print("\n" + "=" * 52)
    print(f"ผ่าน {passed}/{len(_results)} ข้อ")
    if passed < len(_results):
        print("\nข้อที่ต้องแก้")
        for ok, name in _results:
            if not ok:
                print(f"  · {name}")
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
