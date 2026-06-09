import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "email": "newuser@test.com", "display_name": "New User", "password": "Secure1234"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@test.com"
    assert data["auth_source"] == "local"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_without_email(client: AsyncClient):
    # email 為選填
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "noemail", "display_name": "No Email", "password": "Secure1234"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] is None


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    payload = {"username": "dupuser", "display_name": "A", "password": "Secure1234"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "weakpw", "email": "weak@test.com", "display_name": "Weak", "password": "nodigit"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": admin_user.username, "password": "Admin1234"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, admin_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": admin_user.username, "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
