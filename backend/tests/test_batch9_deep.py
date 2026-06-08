"""Batch 9b: deep data scenarios to exercise dashboard loops, project list/overview,
notifications, reactions, subtasks, recurring, milestones remaining branches."""

import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _self_id(client, token):
    return (await client.get("/api/v1/users/me", headers=_auth(token))).json()["id"]


# ── dashboard rich data (exercise overdue/completed/trend/deadline/daily loops) ──
@pytest.mark.asyncio
async def test_dashboard_full_scenario(client: AsyncClient, admin_token: str, project_id: str):
    me = await _self_id(client, admin_token)
    # overdue task (past due, not done, assigned)
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Overdue", "due_date": "2020-01-01", "assignee_ids": [me]},
        headers=_auth(admin_token),
    )
    # done task this week
    done = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Done one", "assignee_ids": [me]},
        headers=_auth(admin_token),
    )
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{done.json()['id']}",
        json={"status": "done"},
        headers=_auth(admin_token),
    )
    # upcoming task (within 7 days)
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Upcoming", "due_date": "2026-06-12", "assignee_ids": [me]},
        headers=_auth(admin_token),
    )
    # project with near end_date
    await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"end_date": "2026-06-15"},
        headers=_auth(admin_token),
    )
    # daily pending + done
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Daily P", "date": "2026-06-08", "labels": [], "status": "pending"},
        headers=_auth(admin_token),
    )
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Daily D", "date": "2026-06-08", "labels": [], "status": "done"},
        headers=_auth(admin_token),
    )

    resp = await client.get("/api/v1/dashboard/summary", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    # endpoint exercises overdue/completed/trend/deadline/daily loops with real data
    assert "kpi" in data
    assert data["kpi"]["completed_this_week"] >= 1
    assert len(data["deadline_projects"]) >= 1


# ── projects list (archived + non) ────────────────────────────────
@pytest.mark.asyncio
async def test_list_projects_archived_filter(client: AsyncClient, admin_token: str, project_id: str):
    # archive the project
    await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"is_archived": True},
        headers=_auth(admin_token),
    )
    active = await client.get("/api/v1/projects/?archived=false", headers=_auth(admin_token))
    archived = await client.get("/api/v1/projects/?archived=true", headers=_auth(admin_token))
    assert active.status_code == 200
    assert archived.status_code == 200
    assert any(p["id"] == project_id for p in archived.json())


@pytest.mark.asyncio
async def test_overview_with_tasks(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get("/api/v1/projects/overview", headers=_auth(admin_token))
    assert resp.status_code == 200
    item = next(p for p in resp.json() if p["id"] == project_id)
    assert item["task_total"] >= 1
    assert item["my_role"] == "owner"


# ── member (non-admin) project access paths ───────────────────────
@pytest.mark.asyncio
async def test_member_sees_own_projects(client: AsyncClient, member_token: str):
    # member creates a project (becomes owner)
    create = await client.post(
        "/api/v1/projects/",
        json={"name": "Member Proj", "color": "#abcabc"},
        headers=_auth(member_token),
    )
    assert create.status_code == 201
    lst = await client.get("/api/v1/projects/", headers=_auth(member_token))
    assert any(p["name"] == "Member Proj" for p in lst.json())
    ov = await client.get("/api/v1/projects/overview", headers=_auth(member_token))
    assert any(p["name"] == "Member Proj" for p in ov.json())


@pytest.mark.asyncio
async def test_member_cannot_delete_others_project(client: AsyncClient, member_token: str, project_id: str):
    # project_id is owned by admin; member is not a member -> 403
    resp = await client.delete(f"/api/v1/projects/{project_id}", headers=_auth(member_token))
    assert resp.status_code == 403


# ── notifications list with project_id resolution ─────────────────
@pytest.mark.asyncio
async def test_notifications_list_resolves_project(
    client: AsyncClient, admin_token: str, member_token: str, member_user, project_id: str, task_id: str
):
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments",
        json={"content": "@Member look here"},
        headers=_auth(admin_token),
    )
    resp = await client.get("/api/v1/notifications/", headers=_auth(member_token))
    assert resp.status_code == 200
    notif = resp.json()["notifications"][0]
    assert notif["project_id"] == project_id


# ── reactions list after toggle ───────────────────────────────────
@pytest.mark.asyncio
async def test_reactions_list_after_add(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, comment_id: str
):
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions/toggle",
        json={"emoji": "🔥"},
        headers=_auth(admin_token),
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions/",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── subtask delete updates parent + not-found paths ───────────────
@pytest.mark.asyncio
async def test_subtask_update_not_found(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    fake = str(uuid.uuid4())
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/{fake}",
        json={"title": "x"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_subtask_delete_recomputes_parent(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    s1 = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/",
        json={"title": "S1"},
        headers=_auth(admin_token),
    )
    await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/{s1.json()['id']}",
        headers=_auth(admin_token),
    )
    parent = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=_auth(admin_token))
    assert parent.json()["subtask_count"] == 0


# ── recurring remove + spawn weekly ───────────────────────────────
@pytest.mark.asyncio
async def test_recurrence_remove_not_found(client: AsyncClient, admin_token: str, project_id: str):
    fake = str(uuid.uuid4())
    resp = await client.delete(f"/api/v1/projects/{project_id}/tasks/{fake}/recurrence", headers=_auth(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recurrence_spawn_with_due_date(client: AsyncClient, admin_token: str, project_id: str):
    t = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Recur me", "due_date": "2026-06-10"},
        headers=_auth(admin_token),
    )
    tid = t.json()["id"]
    await client.put(
        f"/api/v1/projects/{project_id}/tasks/{tid}/recurrence",
        json={"rule": "weekly"},
        headers=_auth(admin_token),
    )
    resp = await client.post(f"/api/v1/projects/{project_id}/tasks/{tid}/recurrence/spawn", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["due_date"] == "2026-06-17"


# ── milestones not-found update ───────────────────────────────────
@pytest.mark.asyncio
async def test_milestone_update_not_found(client: AsyncClient, admin_token: str, project_id: str):
    fake = str(uuid.uuid4())
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/milestones/{fake}",
        json={"note": "x"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404
