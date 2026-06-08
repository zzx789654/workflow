import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_by_task(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # daily task linked to a project task
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Linked daily", "date": "2026-06-10", "labels": [], "linked_task_id": task_id},
        headers=_auth(admin_token),
    )
    resp = await client.get(f"/api/v1/daily-tasks/by-task/{task_id}", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert any(d["title"] == "Linked daily" for d in resp.json())


@pytest.mark.asyncio
async def test_pending_only_filter(client: AsyncClient, admin_token: str):
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Pending one", "date": "2026-01-01", "labels": [], "status": "pending"},
        headers=_auth(admin_token),
    )
    resp = await client.get("/api/v1/daily-tasks/?pending_only=true", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert any(d["title"] == "Pending one" for d in resp.json())


@pytest.mark.asyncio
async def test_update_labels_and_unlink(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    create = await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Relabel", "date": "2026-06-10", "labels": ["a"], "linked_task_id": task_id},
        headers=_auth(admin_token),
    )
    dt_id = create.json()["id"]
    # replace labels
    resp = await client.patch(
        f"/api/v1/daily-tasks/{dt_id}",
        json={"labels": ["x", "y"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert set(resp.json()["labels"]) == {"x", "y"}


@pytest.mark.asyncio
async def test_archive_history_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/daily-tasks/archive/history", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"]["total_records"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_archive_then_history(client: AsyncClient, admin_token: str):
    # create a done daily task, archive it, then read history
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Done task", "date": "2026-01-01", "labels": [], "status": "done", "work_minutes": 45},
        headers=_auth(admin_token),
    )
    arch = await client.post(
        "/api/v1/daily-tasks/archive",
        json={"mode": "done_immediately"},
        headers=_auth(admin_token),
    )
    assert arch.status_code == 200
    assert arch.json()["archived"] >= 1

    hist = await client.get("/api/v1/daily-tasks/archive/history", headers=_auth(admin_token))
    assert hist.status_code == 200
    assert hist.json()["stats"]["total_records"] >= 1
    assert hist.json()["stats"]["total_work_minutes"] >= 45


@pytest.mark.asyncio
async def test_archive_history_export_csv(client: AsyncClient, admin_token: str):
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Done2", "date": "2026-01-02", "labels": [], "status": "done", "work_minutes": 20},
        headers=_auth(admin_token),
    )
    await client.post(
        "/api/v1/daily-tasks/archive",
        json={"mode": "done_immediately"},
        headers=_auth(admin_token),
    )
    resp = await client.get("/api/v1/daily-tasks/archive/history/export", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert "csv" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_archive_blocked_by_unfinished_linked_task(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str
):
    # done daily task linked to a NOT-done project task -> should not archive
    await client.post(
        "/api/v1/daily-tasks/",
        json={
            "title": "Blocked",
            "date": "2026-01-01",
            "labels": [],
            "status": "done",
            "linked_task_id": task_id,
        },
        headers=_auth(admin_token),
    )
    preview = await client.post(
        "/api/v1/daily-tasks/archive/preview",
        json={"mode": "done_immediately"},
        headers=_auth(admin_token),
    )
    assert preview.status_code == 200
    # linked project task is still 'todo', so this daily task is excluded
    assert preview.json()["count"] == 0


@pytest.mark.asyncio
async def test_get_daily_task_not_found(client: AsyncClient, admin_token: str):
    import uuid

    fake = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/daily-tasks/{fake}", headers=_auth(admin_token))
    assert resp.status_code == 404
