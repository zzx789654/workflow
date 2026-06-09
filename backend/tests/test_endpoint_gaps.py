"""跨模組 endpoint gap-fill：非成員 403 / not-found 404 / toggle removed 等易測分支。"""

import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── users ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_update_user_role_not_found(client: AsyncClient, admin_token: str):
    resp = await client.patch(f"/api/v1/users/{uuid.uuid4()}/role?role=member", headers=_auth(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_user_not_found(client: AsyncClient, admin_token: str):
    resp = await client.delete(f"/api/v1/users/{uuid.uuid4()}", headers=_auth(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_self_rejected(client: AsyncClient, admin_token: str):
    me = await client.get("/api/v1/users/me", headers=_auth(admin_token))
    admin_id = me.json()["id"]
    resp = await client.delete(f"/api/v1/users/{admin_id}", headers=_auth(admin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_me(client: AsyncClient, member_token: str):
    resp = await client.patch("/api/v1/users/me", json={"display_name": "Renamed"}, headers=_auth(member_token))
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Renamed"


# ── recurring ──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_recurring_non_member_forbidden(client: AsyncClient, project_id: str, task_id: str, member_token: str):
    resp = await client.put(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/recurrence",
        json={"rule": "daily"},
        headers=_auth(member_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_recurring_set_remove_and_spawn_no_rule(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str
):
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/recurrence"
    # spawn before any rule -> 400
    spawn = await client.post(f"{base}/spawn", headers=_auth(admin_token))
    assert spawn.status_code == 400
    # set then remove
    s = await client.put(base, json={"rule": "weekly"}, headers=_auth(admin_token))
    assert s.status_code == 200
    r = await client.delete(base, headers=_auth(admin_token))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_recurring_task_not_found(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.put(
        f"/api/v1/projects/{project_id}/tasks/{uuid.uuid4()}/recurrence",
        json={"rule": "daily"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


# ── reactions ──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_reaction_toggle_add_then_remove(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, comment_id: str
):
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions"
    add = await client.post(base + "/toggle", json={"emoji": "👍"}, headers=_auth(admin_token))
    assert add.status_code == 200
    assert add.json()["action"] == "added"
    remove = await client.post(base + "/toggle", json={"emoji": "👍"}, headers=_auth(admin_token))
    assert remove.json()["action"] == "removed"


@pytest.mark.asyncio
async def test_reaction_non_member_forbidden(
    client: AsyncClient, project_id: str, task_id: str, comment_id: str, member_token: str
):
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions/",
        headers=_auth(member_token),
    )
    assert resp.status_code == 403


# ── calendar：重複任務略過 + daily label filter ────────────────
@pytest.mark.asyncio
async def test_calendar_with_tasks_and_daily_labels(client: AsyncClient, admin_token: str, project_id: str):
    # a task with a due date + a labelled daily task in range
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Cal Task", "due_date": "2026-06-15"},
        headers=_auth(admin_token),
    )
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Cal Daily", "date": "2026-06-15", "labels": ["work"]},
        headers=_auth(admin_token),
    )
    # label filter exercises the join + post-filter branch
    resp = await client.get("/api/v1/calendar/?year=2026&month=6&label=work", headers=_auth(admin_token))
    assert resp.status_code == 200
