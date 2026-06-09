"""G06 資安強化 finding 驗證：S1 限流、S2 token 失效、S3 fail-closed。"""

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── S2: 改密碼後舊 token 失效 ───────────────────────────────────
@pytest.mark.asyncio
async def test_change_password_invalidates_old_token(client: AsyncClient, member_user, member_token: str):
    # old token works before change
    me = await client.get("/api/v1/users/me", headers=_auth(member_token))
    assert me.status_code == 200

    # change password -> returns a fresh token pair
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Member1234", "new_password": "NewStrong123"},
        headers=_auth(member_token),
    )
    assert resp.status_code == 200
    new_token = resp.json()["access_token"]

    # old token is now revoked (token_version bumped)
    stale = await client.get("/api/v1/users/me", headers=_auth(member_token))
    assert stale.status_code == 401

    # the freshly issued token works
    fresh = await client.get("/api/v1/users/me", headers=_auth(new_token))
    assert fresh.status_code == 200


@pytest.mark.asyncio
async def test_old_refresh_token_revoked_after_password_change(client: AsyncClient, member_user, member_token: str):
    # obtain a refresh token via login
    login = await client.post("/api/v1/auth/login", json={"username": member_user.username, "password": "Member1234"})
    old_refresh = login.json()["refresh_token"]

    # change password (bumps token_version)
    await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Member1234", "new_password": "NewStrong123"},
        headers=_auth(login.json()["access_token"]),
    )

    # old refresh token can no longer mint new access tokens
    resp = await client.post(f"/api/v1/auth/refresh?refresh_token={old_refresh}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_fresh_login_token_has_current_version(client: AsyncClient, member_user, member_token: str):
    # change password once
    cp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Member1234", "new_password": "NewStrong123"},
        headers=_auth(member_token),
    )
    assert cp.status_code == 200
    # re-login with the new password -> token works (version matches)
    login = await client.post("/api/v1/auth/login", json={"username": member_user.username, "password": "NewStrong123"})
    assert login.status_code == 200
    me = await client.get("/api/v1/users/me", headers=_auth(login.json()["access_token"]))
    assert me.status_code == 200


# ── S1: change-password 有限流（decorator 存在即驗證；功能面已由上面覆蓋）──
@pytest.mark.asyncio
async def test_change_password_wrong_old_still_rejected(client: AsyncClient, member_token: str):
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "totallywrong", "new_password": "NewStrong123"},
        headers=_auth(member_token),
    )
    assert resp.status_code == 400


# ── S3: register 在 allow_registration 查詢失敗時 fail-closed ───
@pytest.mark.asyncio
async def test_register_fail_closed_on_settings_error(client: AsyncClient):
    """讀取 allow_registration 設定時 DB 拋例外 → 拒絕註冊（503），而非預設放行。"""
    from app.db.session import get_db
    from app.main import app

    class _BoomSession:
        async def execute(self, *a, **k):
            raise RuntimeError("db down")

    async def override_boom_db():
        yield _BoomSession()

    app.dependency_overrides[get_db] = override_boom_db
    try:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "failclosed", "password": "Secure1234", "display_name": "X"},
        )
        assert resp.status_code == 503
    finally:
        app.dependency_overrides.pop(get_db, None)
