import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.security import decode_token, hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole
from app.websocket.manager import manager

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


async def _ensure_superadmin() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == settings.FIRST_SUPERADMIN_EMAIL))
        if result.scalar_one_or_none():
            return
        admin = User(
            email=settings.FIRST_SUPERADMIN_EMAIL,
            display_name="Administrator",
            hashed_password=hash_password(settings.FIRST_SUPERADMIN_PASSWORD),
            role=UserRole.admin,
        )
        db.add(admin)
        await db.commit()


async def _auto_archive_loop() -> None:
    """每日 00:05 自動封存符合設定的已完成日常任務。"""
    from app.api.v1.endpoints.daily_tasks import run_auto_archive

    while True:
        try:
            now = datetime.now()
            # 計算距下一個 00:05 的秒數
            target = now.replace(hour=0, minute=5, second=0, microsecond=0)
            if now >= target:
                target = target.replace(day=target.day + 1)
            wait_seconds = (target - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            count = await run_auto_archive(AsyncSessionLocal)
            if count > 0:
                logger.info("Auto-archive: moved %d daily tasks to archive", count)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Auto-archive error: %s", exc)
            await asyncio.sleep(3600)  # 出錯後等 1 小時再試


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_superadmin()
    task = asyncio.create_task(_auto_archive_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="WorkFlow API",
    version="1.0.0",
    docs_url=None if settings.APP_ENV == "production" else "/docs",
    redoc_url=None if settings.APP_ENV == "production" else "/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket, token: str = ""):
    """全域通知 WS，每位登入用戶各連一條，用於即時接收跨專案的通知事件。"""
    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=4001)
        return
    await manager.connect(websocket, f"__notif_{user_id}", user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(f"__notif_{user_id}", user_id)


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str, token: str = ""):
    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=4001)
        return
    await manager.connect(websocket, project_id, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(project_id, user_id)
        await manager.broadcast(project_id, {"type": "presence", "user_id": user_id, "action": "left"})


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
