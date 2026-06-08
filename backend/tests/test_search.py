import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/search/?q=nonexistent", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_search_project_by_name(client: AsyncClient, admin_token: str):
    await client.post(
        "/api/v1/projects/",
        json={"name": "SearchTarget", "color": "#333333"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get("/api/v1/search/?q=SearchTarget", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    assert any(r["type"] == "project" and "SearchTarget" in r["title"] for r in data["results"])


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/search/?q=test")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_search_daily_task_by_title(client: AsyncClient, admin_token: str):
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "UniqueSearchDaily", "date": "2026-06-10", "labels": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get("/api/v1/search/?q=UniqueSearchDaily", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["type"] == "daily" and "UniqueSearchDaily" in r["title"] for r in data["results"])
