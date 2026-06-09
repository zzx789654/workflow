"""補測：deps.get_current_user token 邊界、config 生產驗證、auth refresh/except 分支。"""

import uuid

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.security import create_access_token, create_refresh_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── deps.get_current_user 邊界 ─────────────────────────────────
@pytest.mark.asyncio
async def test_invalid_token_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/projects/", headers=_auth("garbage.token.value"))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_malformed_uuid_in_token_rejected(client: AsyncClient):
    # a validly-signed token whose subject is not a UUID
    bad = create_access_token("not-a-uuid")
    resp = await client.get("/api/v1/projects/", headers=_auth(bad))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_for_nonexistent_user_rejected(client: AsyncClient):
    ghost = create_access_token(str(uuid.uuid4()))
    resp = await client.get("/api/v1/projects/", headers=_auth(ghost))
    assert resp.status_code == 401


# ── config.validate_production_secrets ─────────────────────────
def test_config_production_weak_secret_rejected():
    s = Settings(APP_ENV="production", SECRET_KEY="dev_secret_key_change_in_production")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        s.validate_production_secrets()


def test_config_production_weak_password_rejected():
    s = Settings(
        APP_ENV="production",
        SECRET_KEY="a-strong-unique-secret",
        FIRST_SUPERADMIN_PASSWORD="admin123456",
    )
    with pytest.raises(RuntimeError, match="FIRST_SUPERADMIN_PASSWORD"):
        s.validate_production_secrets()


def test_config_production_strong_secrets_ok():
    s = Settings(
        APP_ENV="production",
        SECRET_KEY="a-strong-unique-secret",
        FIRST_SUPERADMIN_PASSWORD="a-strong-unique-password",
    )
    s.validate_production_secrets()  # no raise


def test_config_cors_origins_list():
    s = Settings(CORS_ORIGINS="http://a.com, http://b.com")
    assert s.cors_origins_list == ["http://a.com", "http://b.com"]


# ── auth refresh ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client: AsyncClient):
    resp = await client.post("/api/v1/auth/refresh?refresh_token=bad")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_for_nonexistent_user(client: AsyncClient):
    rt = create_refresh_token(str(uuid.uuid4()))
    resp = await client.post(f"/api/v1/auth/refresh?refresh_token={rt}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient, admin_token: str, admin_user):
    # log in to get a valid refresh token, then refresh
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": admin_user.username, "password": "Admin1234"},
    )
    rt = login.json()["refresh_token"]
    resp = await client.post(f"/api/v1/auth/refresh?refresh_token={rt}")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_change_password_wrong_old(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "wrongwrong", "new_password": "NewStrong123"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, member_user, member_token: str):
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Member1234", "new_password": "NewStrong123"},
        headers=_auth(member_token),
    )
    assert resp.status_code == 200
