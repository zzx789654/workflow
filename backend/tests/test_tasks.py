import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_tasks_empty(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Write docs", "priority": "high"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Write docs"
    assert data["priority"] == "high"
    assert data["status"] == "todo"


@pytest.mark.asyncio
async def test_get_task(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


@pytest.mark.asyncio
async def test_get_task_not_found(client: AsyncClient, admin_token: str, project_id: str):
    import uuid

    fake = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{fake}", headers=_auth(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_task(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"progress": 50, "description": "halfway"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["progress"] == 50


@pytest.mark.asyncio
async def test_update_task_to_done_records_milestone(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str
):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"status": "done"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_move_task(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/move",
        json={"status": "in_progress", "position": 2},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    assert resp.json()["position"] == 2


@pytest.mark.asyncio
async def test_move_task_to_done(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/move",
        json={"status": "done", "position": 0},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.delete(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=_auth(admin_token))
    assert resp.status_code == 204
    # confirm gone
    get_resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=_auth(admin_token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_add_comment(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments",
        json={"content": "Looks good"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["content"] == "Looks good"


@pytest.mark.asyncio
async def test_create_task_with_assignee(client: AsyncClient, admin_token: str, project_id: str, member_user):
    # add member to project first
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Assigned task", "assignee_ids": [member_user.id]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert len(resp.json()["assignees"]) == 1


@pytest.mark.asyncio
async def test_task_requires_membership(client: AsyncClient, member_token: str, project_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/", headers=_auth(member_token))
    assert resp.status_code == 403
