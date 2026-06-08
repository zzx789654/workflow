import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _make_task(client, token, project_id, title):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": title},
        headers=_auth(token),
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_bulk_update_status(client: AsyncClient, admin_token: str, project_id: str):
    t1 = await _make_task(client, admin_token, project_id, "A")
    t2 = await _make_task(client, admin_token, project_id, "B")
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/bulk",
        json={"task_ids": [t1, t2], "status": "in_progress"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_bulk_update_priority(client: AsyncClient, admin_token: str, project_id: str):
    t1 = await _make_task(client, admin_token, project_id, "P")
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/bulk",
        json={"task_ids": [t1], "priority": "urgent"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.asyncio
async def test_bulk_delete(client: AsyncClient, admin_token: str, project_id: str):
    t1 = await _make_task(client, admin_token, project_id, "D1")
    t2 = await _make_task(client, admin_token, project_id, "D2")
    resp = await client.request(
        "DELETE",
        f"/api/v1/projects/{project_id}/tasks/bulk",
        json={"task_ids": [t1, t2]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_bulk_update_no_tasks_found(client: AsyncClient, admin_token: str, project_id: str):
    import uuid

    fake = str(uuid.uuid4())
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/bulk",
        json={"task_ids": [fake], "status": "done"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404
