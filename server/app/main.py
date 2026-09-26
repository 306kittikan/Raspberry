"""จุดเริ่มของเซิร์ฟเวอร์ตู้บริการข้อมูลอัจฉริยะ

รันตอนพัฒนา:  uvicorn app.main:app --reload --port 8000   (จาก server/)
รันบนตู้:      uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, deps
from .events import hub
from .routers import assistant, auth, kiosk, me, sim

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s · %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kiosk")

WEB_DIST = config.ROOT_DIR / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    deps.open_db()
    log.info("ฐานข้อมูล: %s", config.DB_PATH)
    log.info("ผู้ช่วย AI: %s", "พร้อมใช้งาน" if config.AI_ENABLED else "ปิดอยู่ (ไม่มีกุญแจ)")
    if config.SIM_MODE:
        log.warning("โหมดจำลองเปิดอยู่ — ห้ามเปิดโหมดนี้บนตู้ที่ให้บริการจริง")
    yield
    deps.close_db()


app = FastAPI(
    title="ตู้บริการข้อมูลอัจฉริยะ · วิทยาการคอมพิวเตอร์ ม.แม่โจ้",
    version="0.1.0",
    lifespan=lifespan,
)

# ตอนพัฒนา หน้าเว็บรันคนละพอร์ตกับ API จึงต้องเปิด CORS ให้เฉพาะ origin ของ Vite
# ตอนใช้งานจริงเสิร์ฟจาก origin เดียวกัน ส่วนนี้จึงไม่มีผล
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.DEV_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kiosk.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(assistant.router)
if config.SIM_MODE:
    app.include_router(sim.router)


@app.websocket("/ws/kiosk")
async def kiosk_socket(ws: WebSocket) -> None:
    """หน้าจอเปิดค้างไว้เพื่อรับเหตุการณ์จากกล้อง ไมโครโฟน และเซ็นเซอร์"""
    await hub.join(ws)
    try:
        while True:
            # ฝั่งหน้าจอส่งอะไรมาก็ถือเป็นสัญญาณว่ายังมีชีวิตอยู่
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(ws)


# ---- เสิร์ฟหน้าเว็บที่ build แล้ว (มีเฉพาะตอนติดตั้งใช้งานจริง) ----
if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """ทุกเส้นทางที่ไม่ใช่ API คืน index.html ให้ฝั่งหน้าเว็บจัดการเอง"""
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
