import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_time_logs_empty(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_start_and_stop_timer(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    start = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/start",
        json={"note": "working"},
        headers=_auth(admin_token),
    )
    assert start.status_code == 201
    log_id = start.json()["id"]
    stop = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/{log_id}/stop",
        headers=_auth(admin_token),
    )
    assert stop.status_code == 200
    assert stop.json()["ended_at"] is not None


@pytest.mark.asyncio
async def test_start_timer_twice_conflict(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/start",
        json={},
        headers=_auth(admin_token),
    )
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/start",
        json={},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_log_manual(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/manual",
        json={"minutes": 90, "note": "manual entry"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["minutes"] == 90


@pytest.mark.asyncio
async def test_delete_time_log(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    create = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/manual",
        json={"minutes": 30},
        headers=_auth(admin_token),
    )
    log_id = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/{log_id}", headers=_auth(admin_token)
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_time_report(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/manual",
        json={"minutes": 60},
        headers=_auth(admin_token),
    )
    resp = await client.get(f"/api/v1/time-logs/report?project_id={project_id}", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert "report" in resp.json()
