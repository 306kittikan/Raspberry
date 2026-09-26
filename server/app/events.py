"""ช่องทางส่งเหตุการณ์จากเซิร์ฟเวอร์ไปยังหน้าจอตู้

กล้องและไมโครโฟนเป็นฝ่าย "ผลัก" เหตุการณ์เข้ามา (พบคน จำหน้าได้ ได้ยินเสียง)
หน้าเว็บจึงต้องเปิด WebSocket ค้างไว้ แทนที่จะถามเซิร์ฟเวอร์ซ้ำ ๆ
ซึ่งกินซีพียูของ Raspberry Pi โดยเปล่าประโยชน์

ชนิดเหตุการณ์:
  presence       พบ/ไม่พบคนหน้าตู้        → ปลุกจอ หรือเข้าจอพักลึก
  face           ผลการรู้จำใบหน้า          → recognized | unknown | multi | notfound | camera_error
  voice          สถานะไมโครโฟน            → listening | processing | transcript | unclear
  network        สถานะอินเทอร์เน็ต         → online | offline
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("kiosk.events")


class Hub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def join(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        log.info("หน้าจอเชื่อมต่อแล้ว (ทั้งหมด %d)", len(self._clients))

    async def leave(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, kind: str, payload: dict[str, Any] | None = None) -> int:
        """ส่งเหตุการณ์ไปทุกหน้าจอที่เชื่อมต่ออยู่ คืนจำนวนที่ส่งสำเร็จ"""
        message = {"kind": kind, **(payload or {})}
        async with self._lock:
            targets = list(self._clients)

        dead: list[WebSocket] = []
        sent = 0
        for ws in targets:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:  # noqa: BLE001 — หน้าจอหลุดระหว่างส่งเป็นเรื่องปกติ
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)
        return sent


hub = Hub()
