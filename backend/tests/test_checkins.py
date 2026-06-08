import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_checkins_empty(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}/checkins/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_checkin(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/checkins/",
        json={"content": "Made good progress today", "progress": 40},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["progress"] == 40


@pytest.mark.asyncio
async def test_list_checkins_after_create(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/checkins/",
        json={"content": "Update 1", "progress": 10},
        headers=_auth(admin_token),
    )
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}/checkins/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_stale_checkins(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # mark task in_progress so it's a candidate
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"status": "in_progress"},
        headers=_auth(admin_token),
    )
    resp = await client.get("/api/v1/tasks/stale-checkins", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert "stale_tasks" in resp.json()
