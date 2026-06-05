import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/projects/",
        json={"name": "Test Project", "description": "A test", "color": "#ff5733"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Project"
    assert data["color"] == "#ff5733"


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, admin_token: str):
    await client.post(
        "/api/v1/projects/",
        json={"name": "List Test Project"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get("/api/v1/projects/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_project_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/projects/")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_project_invalid_color(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/projects/",
        json={"name": "Bad Color", "color": "notacolor"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
