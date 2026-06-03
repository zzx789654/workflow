"""QA tests for P3 features: attachments, webhooks (project-scoped), recurring tasks, time-log auth."""

import io
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_login(client: AsyncClient, email: str, pw: str = "Pass1234") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email.split("@")[0], "password": pw},
    )
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token2(client: AsyncClient) -> str:
    return await _register_login(client, f"qa_admin_{uuid.uuid4().hex[:6]}@test.com")


@pytest_asyncio.fixture
async def project_task(client: AsyncClient, admin_token2: str) -> dict:
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"QA Project {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token2),
    )
    assert proj.status_code == 201
    project_id = proj.json()["id"]
    task = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "QA Task", "status": "todo", "priority": "medium"},
        headers=auth(admin_token2),
    )
    assert task.status_code == 201
    return {"project_id": project_id, "task_id": task.json()["id"]}


# ── Attachments ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_attachment_upload_list_delete(client: AsyncClient, admin_token2: str, project_task: dict):
    pid, tid = project_task["project_id"], project_task["task_id"]
    base = f"/api/v1/projects/{pid}/tasks/{tid}/attachments"

    # upload
    file_content = b"hello world test file"
    resp = await client.post(
        base + "/",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        headers=auth(admin_token2),
    )
    assert resp.status_code == 201
    att = resp.json()
    assert att["filename"] == "test.txt"
    assert att["file_size"] == len(file_content)
    att_id = att["id"]

    # list
    resp = await client.get(base + "/", headers=auth(admin_token2))
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert att_id in ids

    # download
    resp = await client.get(f"/api/v1/attachments/{att_id}/file", headers=auth(admin_token2))
    assert resp.status_code == 200
    assert resp.content == file_content

    # delete
    resp = await client.delete(base + f"/{att_id}", headers=auth(admin_token2))
    assert resp.status_code == 204

    # confirm gone
    resp = await client.get(base + "/", headers=auth(admin_token2))
    assert att_id not in [a["id"] for a in resp.json()]


@pytest.mark.asyncio
async def test_attachment_requires_auth(client: AsyncClient, project_task: dict):
    pid, tid = project_task["project_id"], project_task["task_id"]
    resp = await client.get(f"/api/v1/projects/{pid}/tasks/{tid}/attachments/")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_attachment_non_member_forbidden(client: AsyncClient, project_task: dict):
    pid, tid = project_task["project_id"], project_task["task_id"]
    outsider = await _register_login(client, f"outsider_{uuid.uuid4().hex[:6]}@test.com")
    resp = await client.get(f"/api/v1/projects/{pid}/tasks/{tid}/attachments/", headers=auth(outsider))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_attachment_download_not_found(client: AsyncClient, admin_token2: str):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/attachments/{fake_id}/file", headers=auth(admin_token2))
    assert resp.status_code == 404


# ── Webhooks (project-scoped) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_project_crud(client: AsyncClient, admin_token2: str, project_task: dict):
    pid = project_task["project_id"]
    base = f"/api/v1/projects/{pid}/webhooks"

    # create
    resp = await client.post(
        base + "/",
        json={"url": "https://example.com/hook", "events": ["task.created", "task.updated"]},
        headers=auth(admin_token2),
    )
    assert resp.status_code == 201
    wh = resp.json()
    assert wh["url"] == "https://example.com/hook"
    assert set(wh["events"]) == {"task.created", "task.updated"}
    assert wh["is_active"] is True
    wh_id = wh["id"]

    # list
    resp = await client.get(base + "/", headers=auth(admin_token2))
    assert resp.status_code == 200
    assert any(w["id"] == wh_id for w in resp.json())

    # update (toggle active)
    resp = await client.patch(base + f"/{wh_id}", json={"is_active": False}, headers=auth(admin_token2))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # delete
    resp = await client.delete(base + f"/{wh_id}", headers=auth(admin_token2))
    assert resp.status_code == 204

    resp = await client.get(base + "/", headers=auth(admin_token2))
    assert all(w["id"] != wh_id for w in resp.json())


@pytest.mark.asyncio
async def test_webhook_test_endpoint(client: AsyncClient, admin_token2: str, project_task: dict):
    pid = project_task["project_id"]
    base = f"/api/v1/projects/{pid}/webhooks"

    resp = await client.post(
        base + "/",
        json={"url": "https://httpbin.org/post", "events": ["task.created"]},
        headers=auth(admin_token2),
    )
    assert resp.status_code == 201
    wh_id = resp.json()["id"]

    # test endpoint should return structured response even on network failure
    resp = await client.post(base + f"/{wh_id}/test", headers=auth(admin_token2))
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert "detail" in data


@pytest.mark.asyncio
async def test_webhook_non_member_forbidden(client: AsyncClient, project_task: dict):
    pid = project_task["project_id"]
    outsider = await _register_login(client, f"wh_outsider_{uuid.uuid4().hex[:6]}@test.com")
    resp = await client.get(f"/api/v1/projects/{pid}/webhooks/", headers=auth(outsider))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_requires_auth(client: AsyncClient, project_task: dict):
    pid = project_task["project_id"]
    resp = await client.get(f"/api/v1/projects/{pid}/webhooks/")
    assert resp.status_code == 403


# ── Recurring Task Fields ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_recurrence_rule_stored(client: AsyncClient, admin_token2: str, project_task: dict):
    pid = project_task["project_id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/tasks/",
        json={
            "title": "Daily Standup",
            "status": "todo",
            "priority": "medium",
            "recurrence_rule": "daily",
            "recurrence_end_date": "2026-12-31",
        },
        headers=auth(admin_token2),
    )
    assert resp.status_code == 201
    task = resp.json()
    assert task["recurrence_rule"] == "daily"
    assert task["recurrence_end_date"] == "2026-12-31"


@pytest.mark.asyncio
async def test_task_recurrence_rule_optional(client: AsyncClient, admin_token2: str, project_task: dict):
    """Tasks without recurrence_rule should still be created normally."""
    pid = project_task["project_id"]
    resp = await client.post(
        f"/api/v1/projects/{pid}/tasks/",
        json={"title": "One-time Task", "status": "todo", "priority": "low"},
        headers=auth(admin_token2),
    )
    assert resp.status_code == 201
    task = resp.json()
    assert task.get("recurrence_rule") is None


@pytest.mark.asyncio
async def test_task_recurrence_update(client: AsyncClient, admin_token2: str, project_task: dict):
    pid, tid = project_task["project_id"], project_task["task_id"]
    resp = await client.patch(
        f"/api/v1/projects/{pid}/tasks/{tid}",
        json={"recurrence_rule": "weekly", "recurrence_end_date": "2026-09-01"},
        headers=auth(admin_token2),
    )
    assert resp.status_code == 200
    assert resp.json()["recurrence_rule"] == "weekly"


# ── Time-Log Auth (security regression) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_time_report_own_data(client: AsyncClient, admin_token2: str):
    resp = await client.get("/api/v1/time-logs/report", headers=auth(admin_token2))
    assert resp.status_code == 200
    data = resp.json()
    # endpoint returns either a list or {"report": [...]}
    assert isinstance(data, (list, dict))


@pytest.mark.asyncio
async def test_time_report_other_user_non_admin_forbidden(client: AsyncClient):
    user1_token = await _register_login(client, f"tluser1_{uuid.uuid4().hex[:6]}@test.com")
    user2_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"tluser2_{uuid.uuid4().hex[:6]}@test.com",
            "display_name": "TLUser2",
            "password": "Pass1234",
        },
    )
    user2_id = user2_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/time-logs/report?user_id={user2_id}",
        headers=auth(user1_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_time_report_admin_can_view_any_user(client: AsyncClient, admin_token: str):
    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"tlother_{uuid.uuid4().hex[:6]}@test.com",
            "display_name": "OtherUser",
            "password": "Pass1234",
        },
    )
    other_id = other.json()["id"]
    resp = await client.get(
        f"/api/v1/time-logs/report?user_id={other_id}",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
