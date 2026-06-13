import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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
        # superadmin 登入帳號取 email 的 @ 前綴；admin 一律 local 來源（保有逃生門）
        admin_email = settings.FIRST_SUPERADMIN_EMAIL
        admin_username = admin_email.split("@")[0] if "@" in admin_email else admin_email
        result = await db.execute(select(User).where(User.username == admin_username))
        if result.scalar_one_or_none():
            return
        admin = User(
            username=admin_username,
            email=admin_email,
            display_name="Administrator",
            hashed_password=hash_password(settings.FIRST_SUPERADMIN_PASSWORD),
            role=UserRole.admin,
            auth_source="local",
        )
        db.add(admin)
        try:
            await db.commit()
        except IntegrityError:
            # 多 worker（uvicorn --workers N）首次啟動時可能同時通過上面的
            # 存在性檢查並各自 INSERT；後到者會撞 username/email unique constraint。
            # 此時代表另一個 worker 已建好 admin，視為成功、回滾本次即可。
            await db.rollback()


async def _auto_archive_loop() -> None:  # pragma: no cover - 無窮排程迴圈，核心 run_auto_archive 已另行單元測
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


async def _ad_sync_loop() -> None:  # pragma: no cover - 無窮排程迴圈，核心 sync_ad_org_tree 已另行單元測
    """每日 01:00 自動同步 AD/OU 組織樹（僅 auth_backend=ldap 時實際動作）。"""
    from app.core.ad_sync import sync_ad_org_tree

    while True:
        try:
            now = datetime.now()
            target = now.replace(hour=1, minute=0, second=0, microsecond=0)
            if now >= target:
                target = target.replace(day=target.day + 1)
            await asyncio.sleep((target - now).total_seconds())
            async with AsyncSessionLocal() as db:
                summary = await sync_ad_org_tree(db)
            logger.info("AD sync: %s", summary.message)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("AD sync error: %s", exc)
            await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover - 啟動/收尾序列，測試以 dependency override 跳過
    await _ensure_superadmin()
    tasks = [asyncio.create_task(_auto_archive_loop()), asyncio.create_task(_ad_sync_loop())]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
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
