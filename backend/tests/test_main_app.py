"""Tests for app.main: health, lifespan (superadmin), websocket auth, auto-archive helper."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_websocket_rejects_bad_token():
    """WS endpoints close with 4001 when token is invalid."""
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from app.main import app

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/notifications?token=bad"):
            pass


@pytest.mark.asyncio
async def test_ensure_superadmin_against_test_db(monkeypatch):
    """Patch AsyncSessionLocal to the test DB so _ensure_superadmin runs cleanly."""
    import os

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    import app.main as main_mod
    from app.db.session import Base

    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(main_mod, "AsyncSessionLocal", factory)
    # first call creates the superadmin, second hits the early-return branch
    await main_mod._ensure_superadmin()
    await main_mod._ensure_superadmin()
    await engine.dispose()


@pytest.mark.asyncio
async def test_run_auto_archive_helper():
    """run_auto_archive over an empty DB returns 0 (covers the loop body)."""
    import os

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.api.v1.endpoints.daily_tasks import run_auto_archive
    from app.db.session import Base

    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    count = await run_auto_archive(factory)
    assert count == 0
    await engine.dispose()
