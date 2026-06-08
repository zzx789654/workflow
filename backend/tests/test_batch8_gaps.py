"""Batch 8: fill coverage gaps across tasks, templates, daily_tasks, system_settings,
recurring, search, milestones, subtasks error paths."""

import io
import uuid

import pytest
from httpx import AsyncClient
from openpyxl import Workbook


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── tasks edge ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_task_update_with_assignees(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, member_user
):
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"assignee_ids": [member_user.id], "title": "Reassigned"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert len(resp.json()["assignees"]) == 1


@pytest.mark.asyncio
async def test_task_status_progress_notify(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # status + progress change triggers notification helper path
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"status": "in_progress", "progress": 30},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200


# ── templates edge ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_apply_template_no_start_date(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/project-templates/",
        json={"name": "NoDate", "tasks": [{"title": "X", "day_offset_start": 0, "day_offset_end": 3}]},
        headers=_auth(admin_token),
    )
    tid = create.json()["id"]
    resp = await client.post(
        f"/api/v1/project-templates/{tid}/apply",
        json={"project_name": "Applied NoDate"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_apply_template_creates_tasks(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/project-templates/",
        json={
            "name": "MultiTask",
            "tasks": [
                {"title": "First", "day_offset_start": 0, "day_offset_end": 1},
                {"title": "Second", "day_offset_start": 2, "day_offset_end": 4, "depends_on_position": 0},
            ],
        },
        headers=_auth(admin_token),
    )
    tid = create.json()["id"]
    applied = await client.post(
        f"/api/v1/project-templates/{tid}/apply",
        json={"project_name": "Multi Applied", "start_date": "2026-06-10"},
        headers=_auth(admin_token),
    )
    assert applied.status_code == 201
    pid = applied.json()["id"]
    tasks = await client.get(f"/api/v1/projects/{pid}/tasks/", headers=_auth(admin_token))
    assert len(tasks.json()) == 2


# ── daily_tasks export csv ────────────────────────────────────────
@pytest.mark.asyncio
async def test_daily_task_import_template_and_roundtrip(client: AsyncClient, admin_token: str):
    # download template, then import a file
    tmpl = await client.get("/api/v1/daily-tasks/import/template", headers=_auth(admin_token))
    assert tmpl.status_code == 200

    wb = Workbook()
    ws = wb.active
    ws.append(["標題", "日期", "狀態", "進度%", "標籤", "說明", "工作分鐘數"])
    ws.append(["RT task", "2026-06-10", "待辦", 0, "tag1,tag2", "desc", 25])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        "/api/v1/daily-tasks/import/excel",
        files={"file": ("rt.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 1


# ── system settings secret roundtrip ──────────────────────────────
@pytest.mark.asyncio
async def test_settings_secret_masked(client: AsyncClient, admin_token: str):
    # set a secret key, then list should mask it
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"ldap_bind_password": "topsecret", "auth_backend": "local"}},
        headers=_auth(admin_token),
    )
    lst = await client.get("/api/v1/system-settings/", headers=_auth(admin_token))
    assert lst.status_code == 200
    secret_row = next((s for s in lst.json() if s["key"] == "ldap_bind_password"), None)
    assert secret_row is not None
    assert secret_row["is_secret"] is True
    assert secret_row["value"] == "••••••••"


@pytest.mark.asyncio
async def test_settings_skip_masked_placeholder(client: AsyncClient, admin_token: str):
    # sending the mask placeholder should not overwrite
    resp = await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"ldap_bind_password": "••••••••"}},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_test_ldap_no_host(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/system-settings/test-ldap",
        json={"username": "u", "password": "p"},
        headers=_auth(admin_token),
    )
    # host not configured -> 400
    assert resp.status_code == 400


# ── recurring monthly + remove on non-existent ────────────────────
@pytest.mark.asyncio
async def test_recurrence_monthly_spawn(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    await client.put(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/recurrence",
        json={"rule": "monthly"},
        headers=_auth(admin_token),
    )
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/recurrence/spawn", headers=_auth(admin_token)
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_recurrence_set_task_not_found(client: AsyncClient, admin_token: str, project_id: str):
    fake = str(uuid.uuid4())
    resp = await client.put(
        f"/api/v1/projects/{project_id}/tasks/{fake}/recurrence",
        json={"rule": "daily"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


# ── search task path ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_search_task_by_title(client: AsyncClient, admin_token: str, project_id: str):
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "FindableTaskXYZ"},
        headers=_auth(admin_token),
    )
    resp = await client.get("/api/v1/search/?q=FindableTaskXYZ", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert any(r["type"] == "task" for r in resp.json()["results"])


@pytest.mark.asyncio
async def test_search_type_filter(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get("/api/v1/search/?q=Fixture&type=project", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert all(r["type"] == "project" for r in resp.json()["results"])


# ── subtask nesting limit ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_subtask_nesting_limit(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    sub = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/",
        json={"title": "L1"},
        headers=_auth(admin_token),
    )
    sub_id = sub.json()["id"]
    # try to nest under the subtask -> 400
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{sub_id}/subtasks/",
        json={"title": "L2"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


# ── checkins stale with member ────────────────────────────────────
@pytest.mark.asyncio
async def test_dependency_target_not_found(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    fake = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/",
        json={"to_task_id": fake},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404
