"""Batch 5: calendar, workload, insights, weekly_report, announcements,
recurring, system_settings, users — broad endpoint coverage."""

import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── calendar ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_calendar_events(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get("/api/v1/calendar/?year=2026&month=6", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_calendar_with_task(client: AsyncClient, admin_token: str, project_id: str):
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Due task", "due_date": "2026-06-15"},
        headers=_auth(admin_token),
    )
    resp = await client.get("/api/v1/calendar/?year=2026&month=6", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert any(e["title"] == "Due task" for e in resp.json())


# ── workload ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_workload_week(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/workload?period=week", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["period"] == "week"
    assert "members" in resp.json()


@pytest.mark.asyncio
async def test_workload_month(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/workload?period=month", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["period"] == "month"


# ── insights ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_insights(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/insights", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "done_trend" in data
    assert "task_summary" in data


# ── weekly report ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_weekly_report(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/weekly-report", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "markdown" in data
    assert "done_count" in data


# ── announcements ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_announcement_lifecycle(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/announcements/",
        json={"title": "Maintenance", "content": "Down at 2am"},
        headers=_auth(admin_token),
    )
    assert create.status_code == 201
    ann_id = create.json()["id"]

    lst = await client.get("/api/v1/announcements/", headers=_auth(admin_token))
    assert lst.status_code == 200
    assert any(a["id"] == ann_id for a in lst.json())

    read = await client.post(f"/api/v1/announcements/{ann_id}/read", headers=_auth(admin_token))
    assert read.status_code == 200

    delete = await client.delete(f"/api/v1/announcements/{ann_id}", headers=_auth(admin_token))
    assert delete.status_code == 204


@pytest.mark.asyncio
async def test_announcement_non_admin_forbidden(client: AsyncClient, member_token: str):
    resp = await client.post(
        "/api/v1/announcements/",
        json={"title": "X", "content": "Y"},
        headers=_auth(member_token),
    )
    assert resp.status_code == 403


# ── recurring ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_set_and_remove_recurrence(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    set_resp = await client.put(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/recurrence",
        json={"rule": "weekly"},
        headers=_auth(admin_token),
    )
    assert set_resp.status_code == 200
    assert set_resp.json()["recurrence_rule"] == "weekly"

    rm = await client.delete(f"/api/v1/projects/{project_id}/tasks/{task_id}/recurrence", headers=_auth(admin_token))
    assert rm.status_code == 200
    assert rm.json()["recurrence_rule"] is None


@pytest.mark.asyncio
async def test_spawn_without_rule_fails(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/recurrence/spawn", headers=_auth(admin_token)
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_spawn_with_rule(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    await client.put(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/recurrence",
        json={"rule": "daily"},
        headers=_auth(admin_token),
    )
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/recurrence/spawn", headers=_auth(admin_token)
    )
    assert resp.status_code == 200
    assert "spawned_task_id" in resp.json()


# ── system settings ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_settings(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/system-settings/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_update_settings(client: AsyncClient, admin_token: str):
    resp = await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"site_name": "My WorkFlow"}},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_settings_non_admin_forbidden(client: AsyncClient, member_token: str):
    resp = await client.get("/api/v1/system-settings/", headers=_auth(member_token))
    assert resp.status_code == 403


# ── users ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_update_me(client: AsyncClient, admin_token: str):
    resp = await client.patch(
        "/api/v1/users/me",
        json={"display_name": "Renamed Admin"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Renamed Admin"


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/users/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_update_user_role(client: AsyncClient, admin_token: str, member_user):
    resp = await client.patch(
        f"/api/v1/users/{member_user.id}/role?role=admin",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_update_user_role_non_admin(client: AsyncClient, member_token: str, admin_user):
    # member trying to change roles -> 403
    fake = str(uuid.uuid4())
    resp = await client.patch(f"/api/v1/users/{fake}/role?role=admin", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_user(client: AsyncClient, admin_token: str, member_user):
    resp = await client.delete(f"/api/v1/users/{member_user.id}", headers=_auth(admin_token))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_deactivate_self_fails(client: AsyncClient, admin_token: str, admin_user):
    me = await client.get("/api/v1/users/me", headers=_auth(admin_token))
    my_id = me.json()["id"]
    resp = await client.delete(f"/api/v1/users/{my_id}", headers=_auth(admin_token))
    assert resp.status_code == 400
