import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_notifications_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/notifications/", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["unread"] == 0
    assert data["notifications"] == []


@pytest.mark.asyncio
async def test_mention_creates_notification(
    client: AsyncClient, admin_token: str, member_token: str, member_user, project_id: str, task_id: str
):
    # add member to project
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    # admin mentions "Member" in a comment
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments",
        json={"content": "hey @Member please review"},
        headers=_auth(admin_token),
    )
    # member should have a notification
    resp = await client.get("/api/v1/notifications/", headers=_auth(member_token))
    assert resp.status_code == 200
    assert resp.json()["unread"] >= 1


@pytest.mark.asyncio
async def test_mark_read(
    client: AsyncClient, admin_token: str, member_token: str, member_user, project_id: str, task_id: str
):
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments",
        json={"content": "@Member ping"},
        headers=_auth(admin_token),
    )
    notifs = (await client.get("/api/v1/notifications/", headers=_auth(member_token))).json()
    notif_id = notifs["notifications"][0]["id"]
    resp = await client.patch(f"/api/v1/notifications/{notif_id}/read", headers=_auth(member_token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_mark_read_not_found(client: AsyncClient, admin_token: str):
    fake = str(uuid.uuid4())
    resp = await client.patch(f"/api/v1/notifications/{fake}/read", headers=_auth(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mark_all_read(client: AsyncClient, member_token: str):
    resp = await client.patch("/api/v1/notifications/read-all", headers=_auth(member_token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
