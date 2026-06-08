import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "kpi" in data
    assert "todo" in data["kpi"]
    assert "overdue" in data["kpi"]
    assert "completed_this_week" in data["kpi"]
    assert "today_due" in data
    assert "action_required" in data
    assert "deadline_projects" in data


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code in (401, 403)
