import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_subtasks_empty(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_subtask(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/",
        json={"title": "Sub 1"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Sub 1"
    assert resp.json()["parent_task_id"] == task_id


@pytest.mark.asyncio
async def test_create_subtask_parent_not_found(client: AsyncClient, admin_token: str, project_id: str):
    fake = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{fake}/subtasks/",
        json={"title": "Orphan"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_subtask(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    create = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/",
        json={"title": "Sub edit"},
        headers=_auth(admin_token),
    )
    sub_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/{sub_id}",
        json={"status": "done", "progress": 100},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_delete_subtask(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    create = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/",
        json={"title": "Sub del"},
        headers=_auth(admin_token),
    )
    sub_id = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/{sub_id}", headers=_auth(admin_token)
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_subtask_counts_update_parent(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # create 2 subtasks, complete 1, parent progress should be 50
    s1 = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/",
        json={"title": "A"},
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/",
        json={"title": "B"},
        headers=_auth(admin_token),
    )
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/{s1.json()['id']}",
        json={"status": "done"},
        headers=_auth(admin_token),
    )
    parent = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=_auth(admin_token))
    assert parent.json()["subtask_count"] == 2
    assert parent.json()["subtask_done_count"] == 1
