import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "todo_count" in data
    assert "overdue_count" in data
    assert "completed_count" in data
    assert "trend" in data
    assert "daily_tasks" in data


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code in (401, 403)
