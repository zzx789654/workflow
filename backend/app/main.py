from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_superadmin()
    yield


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
