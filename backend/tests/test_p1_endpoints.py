"""Tests for P1 endpoints — raises coverage above 70%."""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def project_id(client: AsyncClient, admin_token: str) -> str:
    resp = await client.post(
        "/api/v1/projects/",
        json={"name": f"Cov Project {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest_asyncio.fixture
async def task_id(client: AsyncClient, admin_token: str, project_id: str) -> str:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Cov Task", "status": "todo", "priority": "medium"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest_asyncio.fixture
async def second_task_id(client: AsyncClient, admin_token: str, project_id: str) -> str:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Cov Task 2", "status": "todo", "priority": "low"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Daily Tasks ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_daily_task_list_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/daily-tasks/", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_daily_task_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/daily-tasks/")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_daily_task_crud(client: AsyncClient, admin_token: str):
    today = date.today().isoformat()

    # Create with labels
    create_resp = await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "CRUD Daily Task", "date": today, "labels": ["work", "focus"]},
        headers=auth(admin_token),
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["title"] == "CRUD Daily Task"
    assert sorted(data["labels"]) == ["focus", "work"]
    task_id = data["id"]

    # Get
    get_resp = await client.get(f"/api/v1/daily-tasks/{task_id}", headers=auth(admin_token))
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task_id

    # Update
    patch_resp = await client.patch(
        f"/api/v1/daily-tasks/{task_id}",
        json={"progress": 50, "status": "in_progress"},
        headers=auth(admin_token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["progress"] == 50

    # Update labels
    label_resp = await client.patch(
        f"/api/v1/daily-tasks/{task_id}",
        json={"labels": ["updated"]},
        headers=auth(admin_token),
    )
    assert label_resp.status_code == 200
    assert label_resp.json()["labels"] == ["updated"]

    # Delete
    del_resp = await client.delete(f"/api/v1/daily-tasks/{task_id}", headers=auth(admin_token))
    assert del_resp.status_code == 204

    # Confirm deleted
    gone = await client.get(f"/api/v1/daily-tasks/{task_id}", headers=auth(admin_token))
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_daily_task_list_with_date_filter(client: AsyncClient, admin_token: str):
    today = date.today().isoformat()
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Date Filtered Task", "date": today},
        headers=auth(admin_token),
    )
    resp = await client.get(f"/api/v1/daily-tasks/?date={today}", headers=auth(admin_token))
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert "Date Filtered Task" in titles


# ── Milestones ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_milestone_list_empty(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/milestones/", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_milestone_crud(client: AsyncClient, admin_token: str, project_id: str):
    due = (date.today() + timedelta(days=30)).isoformat()

    # Create
    resp = await client.post(
        f"/api/v1/projects/{project_id}/milestones/",
        json={"name": "M1 Milestone", "due_date": due},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "M1 Milestone"
    mid = data["id"]

    # Update
    patch_resp = await client.patch(
        f"/api/v1/projects/{project_id}/milestones/{mid}",
        json={"name": "M1 Updated"},
        headers=auth(admin_token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "M1 Updated"

    # Delete
    del_resp = await client.delete(f"/api/v1/projects/{project_id}/milestones/{mid}", headers=auth(admin_token))
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_milestone_not_found(client: AsyncClient, admin_token: str, project_id: str):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api/v1/projects/{project_id}/milestones/{fake_id}", headers=auth(admin_token))
    assert resp.status_code == 404


# ── Subtasks ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subtask_list_empty(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_subtask_crud(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # Create
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/",
        json={"title": "Sub Task 1"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Sub Task 1"
    subtask_id = data["id"]

    # Update
    patch_resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/{subtask_id}",
        json={"status": "done"},
        headers=auth(admin_token),
    )
    assert patch_resp.status_code == 200

    # Delete
    del_resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/subtasks/{subtask_id}",
        headers=auth(admin_token),
    )
    assert del_resp.status_code == 204


# ── Time Logs ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_time_log_list(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_time_log_manual(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/manual",
        json={"minutes": 30, "note": "Manual work"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["minutes"] == 30


@pytest.mark.asyncio
async def test_time_log_start_stop_delete(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # Start timer
    start_resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/start",
        json={},
        headers=auth(admin_token),
    )
    assert start_resp.status_code == 201
    log_id = start_resp.json()["id"]

    # Stop timer
    stop_resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/{log_id}/stop",
        headers=auth(admin_token),
    )
    assert stop_resp.status_code == 200
    assert stop_resp.json()["ended_at"] is not None

    # Delete log
    del_resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/{log_id}",
        headers=auth(admin_token),
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_time_log_report(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/time-logs/report", headers=auth(admin_token))
    assert resp.status_code == 200
    assert "report" in resp.json()


# ── Notifications ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notifications_list(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/notifications/", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "unread" in data
    assert "notifications" in data


@pytest.mark.asyncio
async def test_notifications_mark_all_read(client: AsyncClient, admin_token: str):
    resp = await client.patch("/api/v1/notifications/read-all", headers=auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_notifications_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/notifications/")
    assert resp.status_code == 403


# ── Custom Fields ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_custom_fields_list(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/fields", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_custom_fields_create_and_delete(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "Priority Level", "field_type": "text"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Priority Level"
    field_id = data["id"]

    del_resp = await client.delete(
        f"/api/v1/projects/{project_id}/fields/{field_id}",
        headers=auth(admin_token),
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_custom_field_values_get(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/field-values",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_custom_field_values_set(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # First create a field
    field_resp = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "Notes", "field_type": "text"},
        headers=auth(admin_token),
    )
    assert field_resp.status_code == 201
    field_id = field_resp.json()["id"]

    # Set value
    resp = await client.put(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/field-values",
        json=[{"field_id": field_id, "value": "Some note"}],
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ── Dashboard ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/dashboard/summary", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "kpi" in data
    assert "trend" in data
    assert "action_required" in data
    assert "todo" in data["kpi"]
    assert len(data["trend"]) == 7


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 403


# ── Search ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_all(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/search/?q=test", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data
    assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_search_type_task(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/search/?q=Cov&type=task", headers=auth(admin_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_type_project(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/search/?q=Cov&type=project", headers=auth(admin_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_type_daily(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/search/?q=Daily&type=daily", headers=auth(admin_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/search/?q=test")
    assert resp.status_code == 403


# ── Templates ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_template_list(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/project-templates/", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_template_crud(client: AsyncClient, admin_token: str):
    # Create
    resp = await client.post(
        "/api/v1/project-templates/",
        json={
            "name": "Sprint Template",
            "description": "A sprint template",
            "tasks": [
                {"title": "Task 1", "priority": "medium", "day_offset_start": 0},
                {"title": "Task 2", "priority": "high", "day_offset_start": 1},
            ],
        },
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Sprint Template"
    assert len(data["tasks"]) == 2
    tmpl_id = data["id"]

    # Get
    get_resp = await client.get(f"/api/v1/project-templates/{tmpl_id}", headers=auth(admin_token))
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == tmpl_id

    # Update
    patch_resp = await client.patch(
        f"/api/v1/project-templates/{tmpl_id}",
        json={"name": "Updated Sprint Template"},
        headers=auth(admin_token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Sprint Template"

    # Delete
    del_resp = await client.delete(f"/api/v1/project-templates/{tmpl_id}", headers=auth(admin_token))
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_template_apply(client: AsyncClient, admin_token: str):
    tmpl_resp = await client.post(
        "/api/v1/project-templates/",
        json={"name": "Apply Template", "tasks": [{"title": "T1", "day_offset_start": 0}]},
        headers=auth(admin_token),
    )
    assert tmpl_resp.status_code == 201
    tmpl_id = tmpl_resp.json()["id"]

    apply_resp = await client.post(
        f"/api/v1/project-templates/{tmpl_id}/apply",
        json={"project_name": "Applied Project"},
        headers=auth(admin_token),
    )
    assert apply_resp.status_code == 201
    assert apply_resp.json()["name"] == "Applied Project"


@pytest.mark.asyncio
async def test_template_from_project(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.post(
        f"/api/v1/project-templates/from-project/{project_id}?name=From+Project+Template",
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    assert "From Project Template" in resp.json()["name"]


# ── Calendar ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_calendar_events(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/calendar/?year=2026&month=6", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_calendar_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/calendar/?year=2026&month=6")
    assert resp.status_code == 403


# ── Dependencies ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dependency_list_empty(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_dependency_add_and_remove(
    client: AsyncClient,
    admin_token: str,
    project_id: str,
    task_id: str,
    second_task_id: str,
):
    # Add dependency task_id → second_task_id
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/",
        json={"to_task_id": second_task_id},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    dep_id = resp.json()["id"]

    # Remove
    del_resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/{dep_id}",
        headers=auth(admin_token),
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_dependency_self_reference_rejected(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/",
        json={"to_task_id": task_id},
        headers=auth(admin_token),
    )
    assert resp.status_code == 400


# ── Tasks extra coverage ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_get_update_delete(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # Get task
    get_resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        headers=auth(admin_token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task_id

    # Update task
    patch_resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"title": "Updated Cov Task", "status": "in_progress"},
        headers=auth(admin_token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Cov Task"

    # Delete task
    del_resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        headers=auth(admin_token),
    )
    assert del_resp.status_code == 204


# ── Auth refresh ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_refresh(client: AsyncClient, admin_user):
    login_resp = await client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin1234"})
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", params={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.json()


# ── Project get / update / delete ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_project_get_update_delete(client: AsyncClient, admin_token: str, project_id: str):
    get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(admin_token))
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == project_id

    patch_resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated Project Name"},
        headers=auth(admin_token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Project Name"

    del_resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth(admin_token))
    assert del_resp.status_code == 204


# ── Project member management ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_project_members(client: AsyncClient, admin_token: str, project_id: str):
    list_resp = await client.get(f"/api/v1/projects/{project_id}/members", headers=auth(admin_token))
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    second_email = f"member_{uuid.uuid4().hex[:6]}@test.com"
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": second_email, "display_name": "Member", "password": "Pass1234"},
    )
    assert reg_resp.status_code == 201
    second_user_id = reg_resp.json()["id"]

    add_resp = await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": second_user_id, "role": "member"},
        headers=auth(admin_token),
    )
    assert add_resp.status_code == 201

    del_resp = await client.delete(
        f"/api/v1/projects/{project_id}/members/{second_user_id}",
        headers=auth(admin_token),
    )
    assert del_resp.status_code == 204


# ── Users endpoints ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_list_and_update_me(client: AsyncClient, admin_token: str):
    list_resp = await client.get("/api/v1/users/", headers=auth(admin_token))
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    patch_resp = await client.patch(
        "/api/v1/users/me",
        json={"display_name": "Admin Updated"},
        headers=auth(admin_token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["display_name"] == "Admin Updated"


@pytest.mark.asyncio
async def test_user_role_and_deactivate(client: AsyncClient, admin_token: str):
    target_email = f"target_{uuid.uuid4().hex[:6]}@test.com"
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": target_email, "display_name": "Target", "password": "Pass1234"},
    )
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["id"]

    role_resp = await client.patch(
        f"/api/v1/users/{user_id}/role",
        params={"role": "viewer"},
        headers=auth(admin_token),
    )
    assert role_resp.status_code == 200
    assert role_resp.json()["role"] == "viewer"

    del_resp = await client.delete(f"/api/v1/users/{user_id}", headers=auth(admin_token))
    assert del_resp.status_code == 204


# ── Task list / move / comment ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_list(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/", headers=auth(admin_token))
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert any(t["id"] == task_id for t in items)


@pytest.mark.asyncio
async def test_task_move(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/move",
        json={"status": "in_progress", "position": 1},
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_task_add_comment(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments",
        json={"content": "A test comment"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["content"] == "A test comment"


@pytest.mark.asyncio
async def test_notification_mark_read_404(client: AsyncClient, admin_token: str):
    fake_id = str(uuid.uuid4())
    resp = await client.patch(f"/api/v1/notifications/{fake_id}/read", headers=auth(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_milestone_list_with_data(client: AsyncClient, admin_token: str, project_id: str):
    due = (date.today() + timedelta(days=10)).isoformat()
    await client.post(
        f"/api/v1/projects/{project_id}/milestones/",
        json={"name": "Coverage Milestone", "due_date": due},
        headers=auth(admin_token),
    )
    resp = await client.get(f"/api/v1/projects/{project_id}/milestones/", headers=auth(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
