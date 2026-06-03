"""Tests for P2 backend features."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _register_login(client: AsyncClient, email: str, pw: str = "Pass1234") -> str:
    """Register a user and return JWT token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email.split("@")[0], "password": pw},
    )
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def member_token(client: AsyncClient) -> str:
    return await _register_login(client, f"member_{uuid.uuid4().hex[:6]}@test.com")


@pytest_asyncio.fixture
async def project_with_task(client: AsyncClient, admin_token: str) -> dict:
    """Create a project with one task, return {project_id, task_id}."""
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"P2 Project {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    task = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Test Task", "status": "todo", "priority": "medium"},
        headers=auth(admin_token),
    )
    assert task.status_code == 201
    task_id = task.json()["id"]
    return {"project_id": project_id, "task_id": task_id}


@pytest_asyncio.fixture
async def project_with_comment(client: AsyncClient, admin_token: str, project_with_task: dict) -> dict:
    """Add a comment to the task, return {project_id, task_id, comment_id}."""
    project_id = project_with_task["project_id"]
    task_id = project_with_task["task_id"]
    comment = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments",
        json={"content": "A comment"},
        headers=auth(admin_token),
    )
    assert comment.status_code == 201
    return {**project_with_task, "comment_id": comment.json()["id"]}


# ── Weekly Reports ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_weekly_report_get(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/reports/weekly", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "week_start" in data
    assert "completed_tasks" in data
    assert "daily_tasks" in data
    assert len(data["daily_tasks"]) == 7


@pytest.mark.asyncio
async def test_weekly_report_save(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/reports/weekly",
        json={"next_week_plan": "Focus on testing"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["next_week_plan"] == "Focus on testing"
    assert "id" in data


@pytest.mark.asyncio
async def test_weekly_report_roundtrip(client: AsyncClient, admin_token: str):
    plan = "Complete all P2 features"
    await client.post(
        "/api/v1/reports/weekly", json={"next_week_plan": plan}, headers=auth(admin_token)
    )
    resp = await client.get("/api/v1/reports/weekly", headers=auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["next_week_plan"] == plan


# ── Workload ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workload_week(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/workload/?period=week", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_workload_month(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/workload/?period=month", headers=auth(admin_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_workload_invalid_period(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/workload/?period=year", headers=auth(admin_token))
    assert resp.status_code == 400


# ── Bulk Actions ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_status_change(client: AsyncClient, admin_token: str, project_with_task: dict):
    project_id = project_with_task["project_id"]
    task_id = project_with_task["task_id"]

    # Create second task
    t2 = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Task 2"},
        headers=auth(admin_token),
    )
    task_id2 = t2.json()["id"]

    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/bulk",
        json={"task_ids": [task_id, task_id2], "action": "status", "value": "in_progress"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 2
    assert data["action"] == "status"


@pytest.mark.asyncio
async def test_bulk_delete(client: AsyncClient, admin_token: str, project_with_task: dict):
    project_id = project_with_task["project_id"]
    task_id = project_with_task["task_id"]

    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/bulk",
        json={"task_ids": [task_id], "action": "delete"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1


@pytest.mark.asyncio
async def test_bulk_invalid_action(client: AsyncClient, admin_token: str, project_with_task: dict):
    project_id = project_with_task["project_id"]
    task_id = project_with_task["task_id"]

    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/bulk",
        json={"task_ids": [task_id], "action": "unknown"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 400


# ── Comment Reactions ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_reaction(client: AsyncClient, admin_token: str, project_with_comment: dict):
    project_id = project_with_comment["project_id"]
    task_id = project_with_comment["task_id"]
    comment_id = project_with_comment["comment_id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions",
        json={"emoji": "👍"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["emoji"] == "👍"


@pytest.mark.asyncio
async def test_add_duplicate_reaction(client: AsyncClient, admin_token: str, project_with_comment: dict):
    project_id = project_with_comment["project_id"]
    task_id = project_with_comment["task_id"]
    comment_id = project_with_comment["comment_id"]

    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions",
        json={"emoji": "🔥"},
        headers=auth(admin_token),
    )
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions",
        json={"emoji": "🔥"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_remove_reaction(client: AsyncClient, admin_token: str, project_with_comment: dict):
    project_id = project_with_comment["project_id"]
    task_id = project_with_comment["task_id"]
    comment_id = project_with_comment["comment_id"]

    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions",
        json={"emoji": "❤️"},
        headers=auth(admin_token),
    )
    resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions/❤️",
        headers=auth(admin_token),
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_remove_nonexistent_reaction(client: AsyncClient, admin_token: str, project_with_comment: dict):
    project_id = project_with_comment["project_id"]
    task_id = project_with_comment["task_id"]
    comment_id = project_with_comment["comment_id"]

    resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions/🦄",
        headers=auth(admin_token),
    )
    assert resp.status_code == 404


# ── Task Checkins ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_checkin(client: AsyncClient, admin_token: str, project_with_task: dict):
    project_id = project_with_task["project_id"]
    task_id = project_with_task["task_id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/checkins/",
        json={"content": "Making progress", "progress": 50},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Making progress"
    assert data["progress"] == 50


@pytest.mark.asyncio
async def test_list_checkins(client: AsyncClient, admin_token: str, project_with_task: dict):
    project_id = project_with_task["project_id"]
    task_id = project_with_task["task_id"]

    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/checkins/",
        json={"content": "Check 1", "progress": 25},
        headers=auth(admin_token),
    )
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/checkins/",
        json={"content": "Check 2", "progress": 75},
        headers=auth(admin_token),
    )

    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/checkins/",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


# ── Announcements ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_announcement_admin(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/announcements/",
        json={"title": "Test Announcement", "content": "Hello everyone"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Announcement"


@pytest.mark.asyncio
async def test_create_announcement_non_admin_forbidden(client: AsyncClient, member_token: str):
    resp = await client.post(
        "/api/v1/announcements/",
        json={"title": "Unauthorized", "content": "Should fail"},
        headers=auth(member_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_announcements(client: AsyncClient, admin_token: str):
    await client.post(
        "/api/v1/announcements/",
        json={"title": "List Test", "content": "Visible"},
        headers=auth(admin_token),
    )
    resp = await client.get("/api/v1/announcements/", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    titles = [a["title"] for a in resp.json()]
    assert "List Test" in titles


@pytest.mark.asyncio
async def test_mark_announcement_read(client: AsyncClient, admin_token: str):
    create_resp = await client.post(
        "/api/v1/announcements/",
        json={"title": "Read Test", "content": "Mark me"},
        headers=auth(admin_token),
    )
    announcement_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/announcements/{announcement_id}/read",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] in ("marked_read", "already_read")

    # Second call should return already_read
    resp2 = await client.post(
        f"/api/v1/announcements/{announcement_id}/read",
        headers=auth(admin_token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "already_read"


# ── Public Share Links ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_share_link(client: AsyncClient, admin_token: str, project_with_task: dict):
    project_id = project_with_task["project_id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/share",
        json={},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert "url" in data


@pytest.mark.asyncio
async def test_access_public_project(client: AsyncClient, admin_token: str, project_with_task: dict):
    project_id = project_with_task["project_id"]

    # Create share link
    share_resp = await client.post(
        f"/api/v1/projects/{project_id}/share",
        json={},
        headers=auth(admin_token),
    )
    assert share_resp.status_code == 201
    token = share_resp.json()["token"]

    # Access without auth
    resp = await client.get(f"/api/v1/public/projects/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert "project" in data
    assert "tasks" in data
    assert isinstance(data["tasks"], list)


@pytest.mark.asyncio
async def test_public_invalid_token(client: AsyncClient):
    resp = await client.get("/api/v1/public/projects/nonexistent-token-xyz")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_share_link_non_member_forbidden(client: AsyncClient, member_token: str):
    """A non-member cannot create a share link for a project."""
    # Create project as admin (done in another test), use a random project_id
    fake_project_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/projects/{fake_project_id}/share",
        json={},
        headers=auth(member_token),
    )
    assert resp.status_code in (403, 404)


# ── User Insights ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_insights(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/users/me/insights", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "completed_30d" in data
    assert "avg_completion_days" in data
    assert "top_hour" in data
    assert "daily_counts" in data
    assert len(data["daily_counts"]) == 30


# ── Project Health Score ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_project_health_score(client: AsyncClient, admin_token: str, project_with_task: dict):
    project_id = project_with_task["project_id"]

    resp = await client.get(
        f"/api/v1/projects/{project_id}/health",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "health_score" in data
    assert 0 <= data["health_score"] <= 100
    assert "breakdown" in data
    assert "details" in data


@pytest.mark.asyncio
async def test_project_health_not_found(client: AsyncClient, admin_token: str):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/projects/{fake_id}/health", headers=auth(admin_token))
    assert resp.status_code == 404


# ── AI Suggestions ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_suggest(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/dashboard/ai-suggest", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    if data:
        assert "task_id" in data[0]
        assert "title" in data[0]
        assert "score" in data[0]
        assert "reason" in data[0]


@pytest.mark.asyncio
async def test_ai_suggest_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/dashboard/ai-suggest")
    assert resp.status_code == 403
