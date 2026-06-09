import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, admin_token: str, admin_user):
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Admin1234", "new_password": "NewPass5678"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    # login with new password works
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": admin_user.username, "password": "NewPass5678"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_old(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "WrongOld99", "new_password": "NewPass5678"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, admin_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": admin_user.username, "password": "Admin1234"},
    )
    refresh = login.json()["refresh_token"]
    resp = await client.post(f"/api/v1/auth/refresh?refresh_token={refresh}")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    resp = await client.post("/api/v1/auth/refresh?refresh_token=garbage.token.here")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(client: AsyncClient, admin_token: str):
    # access token used as refresh -> rejected (expected_type mismatch)
    resp = await client.post(f"/api/v1/auth/refresh?refresh_token={admin_token}")
    assert resp.status_code == 401
