import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_daily_tasks_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/daily-tasks/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_daily_task(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Buy groceries", "date": "2026-06-10", "labels": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_daily_task(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Read book", "date": "2026-06-10", "labels": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    task_id = create.json()["id"]
    resp = await client.get(f"/api/v1/daily-tasks/{task_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Read book"


@pytest.mark.asyncio
async def test_update_daily_task(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Exercise", "date": "2026-06-10", "labels": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    task_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/daily-tasks/{task_id}",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_delete_daily_task(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Clean desk", "date": "2026-06-10", "labels": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    task_id = create.json()["id"]
    resp = await client.delete(f"/api/v1/daily-tasks/{task_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_daily_task_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/daily-tasks/")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_archive_preview(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/daily-tasks/archive/preview",
        json={"mode": "done_immediately"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "cutoff" in data


@pytest.mark.asyncio
async def test_archive_execute(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/daily-tasks/archive",
        json={"mode": "done_immediately"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "archived" in resp.json()


@pytest.mark.asyncio
async def test_daily_task_list_with_label(client: AsyncClient, admin_token: str):
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "Labelled task", "date": "2026-06-10", "labels": ["work"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get("/api/v1/daily-tasks/?label=work", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert any(t["title"] == "Labelled task" for t in resp.json())
