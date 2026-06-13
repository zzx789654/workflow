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


@pytest.mark.asyncio
async def test_list_pagination_limit_offset(client: AsyncClient, admin_token: str):
    """limit/offset 分頁正確切片，且 X-Total-Count 回傳總數。"""
    H = {"Authorization": f"Bearer {admin_token}"}
    for i in range(7):
        await client.post(
            "/api/v1/daily-tasks/",
            json={"title": f"P{i}", "date": "2026-06-13"},
            headers=H,
        )

    # 第一頁
    r1 = await client.get("/api/v1/daily-tasks/?limit=3&offset=0", headers=H)
    assert r1.status_code == 200
    assert r1.headers["X-Total-Count"] == "7"
    page1 = [t["title"] for t in r1.json()]
    assert len(page1) == 3

    # 第二頁
    r2 = await client.get("/api/v1/daily-tasks/?limit=3&offset=3", headers=H)
    page2 = [t["title"] for t in r2.json()]
    assert len(page2) == 3
    assert set(page1).isdisjoint(page2)  # 不重疊

    # 最後一頁（剩 1 筆）
    r3 = await client.get("/api/v1/daily-tasks/?limit=3&offset=6", headers=H)
    assert len(r3.json()) == 1
    assert r3.headers["X-Total-Count"] == "7"


@pytest.mark.asyncio
async def test_list_without_limit_returns_all_with_total_header(client: AsyncClient, admin_token: str):
    """不傳 limit（向後相容）：回傳全部，且仍帶 X-Total-Count。"""
    H = {"Authorization": f"Bearer {admin_token}"}
    for i in range(4):
        await client.post(
            "/api/v1/daily-tasks/",
            json={"title": f"A{i}", "date": "2026-06-13"},
            headers=H,
        )
    resp = await client.get("/api/v1/daily-tasks/", headers=H)
    assert resp.status_code == 200
    assert len(resp.json()) == 4
    assert resp.headers["X-Total-Count"] == "4"


@pytest.mark.asyncio
async def test_list_pagination_with_label_count(client: AsyncClient, admin_token: str):
    """分頁與 label 篩選並用時，X-Total-Count 應只算符合 label 的數量。"""
    H = {"Authorization": f"Bearer {admin_token}"}
    for i in range(3):
        await client.post(
            "/api/v1/daily-tasks/",
            json={"title": f"L{i}", "date": "2026-06-13", "labels": ["urgent"]},
            headers=H,
        )
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "other", "date": "2026-06-13", "labels": ["misc"]},
        headers=H,
    )
    resp = await client.get("/api/v1/daily-tasks/?label=urgent&limit=2&offset=0", headers=H)
    assert resp.status_code == 200
    assert resp.headers["X-Total-Count"] == "3"  # 只算 urgent，不含 misc
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_pagination_limit_bounds(client: AsyncClient, admin_token: str):
    """limit 邊界：0 與超過上限皆 422。"""
    H = {"Authorization": f"Bearer {admin_token}"}
    assert (await client.get("/api/v1/daily-tasks/?limit=0", headers=H)).status_code == 422
    assert (await client.get("/api/v1/daily-tasks/?limit=999", headers=H)).status_code == 422
    assert (await client.get("/api/v1/daily-tasks/?offset=-1", headers=H)).status_code == 422
