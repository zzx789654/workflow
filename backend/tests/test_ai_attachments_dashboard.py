import io

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── ai_assist (rule engine path; no ANTHROPIC_API_KEY in test env) ──
@pytest.mark.asyncio
async def test_ai_suggestions_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/ai/priority-suggestions", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
    assert "model" in data


@pytest.mark.asyncio
async def test_ai_suggestions_with_tasks(client: AsyncClient, admin_token: str, project_id: str, member_user):
    # admin assigns themselves a task with a due date
    me = (await client.get("/api/v1/users/me", headers=_auth(admin_token))).json()
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Urgent thing", "priority": "urgent", "due_date": "2026-06-09", "assignee_ids": [me["id"]]},
        headers=_auth(admin_token),
    )
    resp = await client.get("/api/v1/ai/priority-suggestions", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] in ("rule_engine_v1", "claude-haiku-4-5")
    assert len(data["suggestions"]) >= 1


# ── attachments ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_attachments_empty(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_upload_and_download_attachment(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    content = b"hello world file"
    up = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/",
        files={"file": ("note.txt", io.BytesIO(content), "text/plain")},
        headers=_auth(admin_token),
    )
    assert up.status_code == 201
    att_id = up.json()["id"]

    dl = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/{att_id}/download",
        headers=_auth(admin_token),
    )
    assert dl.status_code == 200
    assert dl.content == content


@pytest.mark.asyncio
async def test_upload_rejects_disallowed_type(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    up = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/",
        files={"file": ("bad.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
        headers=_auth(admin_token),
    )
    assert up.status_code == 415


@pytest.mark.asyncio
async def test_delete_attachment(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    up = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/",
        files={"file": ("x.txt", io.BytesIO(b"data"), "text/plain")},
        headers=_auth(admin_token),
    )
    att_id = up.json()["id"]
    resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/{att_id}", headers=_auth(admin_token)
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_project_files(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/",
        files={"file": ("doc.txt", io.BytesIO(b"content"), "text/plain")},
        headers=_auth(admin_token),
    )
    resp = await client.get(f"/api/v1/projects/{project_id}/files/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ── dashboard with data ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_dashboard_with_tasks_and_daily(client: AsyncClient, admin_token: str, project_id: str):
    me = (await client.get("/api/v1/users/me", headers=_auth(admin_token))).json()
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Due today", "due_date": "2026-06-08", "assignee_ids": [me["id"]]},
        headers=_auth(admin_token),
    )
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Daily pending", "date": "2026-06-08", "labels": [], "status": "pending"},
        headers=_auth(admin_token),
    )
    resp = await client.get("/api/v1/dashboard/summary", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert "today_due" in resp.json()
