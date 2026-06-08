import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_milestones_empty(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/milestones/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_milestone_created_on_task_done(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # mark task done -> milestone log auto-created
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"status": "done"},
        headers=_auth(admin_token),
    )
    resp = await client.get(f"/api/v1/projects/{project_id}/milestones/", headers=_auth(admin_token))
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert any(log["task_id"] == task_id for log in logs)


@pytest.mark.asyncio
async def test_milestone_update_note(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"status": "done"},
        headers=_auth(admin_token),
    )
    logs = (await client.get(f"/api/v1/projects/{project_id}/milestones/", headers=_auth(admin_token))).json()
    log_id = logs[0]["id"]
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/milestones/{log_id}",
        json={"note": "Great work"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["note"] == "Great work"
