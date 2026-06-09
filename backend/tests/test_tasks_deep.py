"""Tasks 深度補測：update 通知分支/assignee 重設/progress、comment @mention、角色權限。"""

import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _add_member(client, admin_token, project_id, user_id, role):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": user_id, "role": role},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_update_task_status_and_progress_notifies(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, member_user
):
    # assign to member so a progress/status change triggers notification path
    await _add_member(client, admin_token, project_id, member_user.id, "member")
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"assignee_ids": [member_user.id]},
        headers=_auth(admin_token),
    )
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"status": "in_progress", "progress": 50},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["progress"] == 50


@pytest.mark.asyncio
async def test_update_task_reassign_clears_old_assignees(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, member_user
):
    await _add_member(client, admin_token, project_id, member_user.id, "member")
    # first assign member
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"assignee_ids": [member_user.id]},
        headers=_auth(admin_token),
    )
    # then reassign to nobody -> old assignee deletion branch
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"assignee_ids": []},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["assignees"] == []


@pytest.mark.asyncio
async def test_add_comment_with_mention(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, member_user
):
    await _add_member(client, admin_token, project_id, member_user.id, "member")
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments",
        json={"content": f"hello @{member_user.email} please check"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_viewer_cannot_create_task(
    client: AsyncClient, admin_token: str, project_id: str, member_user, member_token: str
):
    await _add_member(client, admin_token, project_id, member_user.id, "viewer")
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "blocked"},
        headers=_auth(member_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_delete_task(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, member_user, member_token: str
):
    await _add_member(client, admin_token, project_id, member_user.id, "member")
    resp = await client.delete(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manager_can_delete_task(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, member_user, member_token: str
):
    await _add_member(client, admin_token, project_id, member_user.id, "manager")
    resp = await client.delete(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=_auth(member_token))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_move_task_not_found(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{uuid.uuid4()}/move",
        json={"status": "done", "position": 0},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_task_with_multiple_assignees(client: AsyncClient, admin_token: str, project_id: str, member_user):
    await _add_member(client, admin_token, project_id, member_user.id, "member")
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "multi", "assignee_ids": [member_user.id]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert len(resp.json()["assignees"]) == 1
