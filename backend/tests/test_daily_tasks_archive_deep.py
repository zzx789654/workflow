"""daily_tasks 補測：cutoff 各 mode、history 篩選+關聯名稱、run_auto_archive、admin 視角。"""

import os
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.endpoints.daily_tasks import _compute_cutoff, run_auto_archive
from app.models.user import User

TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://workflow:workflow_pass@localhost:5432/workflow_test",
)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── _compute_cutoff 純函式分支 ─────────────────────────────────
def test_compute_cutoff_modes():
    today = date.today()
    assert _compute_cutoff("done_immediately", None) == today
    assert _compute_cutoff("done_1month", None) == today - timedelta(days=30)
    assert _compute_cutoff("done_3months", None) == today - timedelta(days=90)
    custom = date(2026, 1, 1)
    assert _compute_cutoff("done_custom", custom) == custom


def test_compute_cutoff_custom_requires_before_date():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _compute_cutoff("done_custom", None)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_archive_custom_mode(client: AsyncClient, admin_token: str):
    # create a done daily task in the past, archive with custom cutoff
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "old done", "date": "2026-01-05", "status": "done", "labels": []},
        headers=_auth(admin_token),
    )
    resp = await client.post(
        "/api/v1/daily-tasks/archive",
        json={"mode": "done_custom", "before_date": "2026-02-01"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["archived"] >= 1


@pytest.mark.asyncio
async def test_archive_1month_and_3months_modes(client: AsyncClient, admin_token: str):
    # done task 100 days ago qualifies for both 1month and 3months
    old = (date.today() - timedelta(days=100)).isoformat()
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "very old", "date": old, "status": "done", "labels": []},
        headers=_auth(admin_token),
    )
    resp = await client.post(
        "/api/v1/daily-tasks/archive",
        json={"mode": "done_3months"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["archived"] >= 1


@pytest.mark.asyncio
async def test_history_filters_by_date_and_task(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # the linked project task must be done, otherwise the archive query blocks it
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"status": "done"},
        headers=_auth(admin_token),
    )
    # done daily linked to a (now done) project task -> archive -> history with all filters
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "linked done", "date": "2026-03-01", "status": "done", "labels": [], "linked_task_id": task_id},
        headers=_auth(admin_token),
    )
    await client.post(
        "/api/v1/daily-tasks/archive",
        json={"mode": "done_immediately"},
        headers=_auth(admin_token),
    )
    # filter by date range + linked_task_id -> exercises history filter + task/project name resolution
    resp = await client.get(
        f"/api/v1/daily-tasks/archive/history?date_from=2026-01-01&date_to=2026-12-31&linked_task_id={task_id}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stats"]["total_records"] >= 1
    # linked task/project names resolved
    assert body["items"][0]["linked_task_title"] is not None
    assert body["items"][0]["linked_project_name"] is not None


@pytest.mark.asyncio
async def test_admin_can_view_other_users_daily_task(client: AsyncClient, admin_token: str, member_token: str):
    # member creates a daily task; admin lists with target_user_id
    me = await client.get("/api/v1/users/me", headers=_auth(member_token))
    member_id = me.json()["id"]
    created = await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "member task", "date": "2026-06-10", "labels": []},
        headers=_auth(member_token),
    )
    assert created.status_code == 201
    # admin queries that user's tasks
    resp = await client.get(
        f"/api/v1/daily-tasks/?target_user_id={member_id}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert any(t["title"] == "member task" for t in resp.json())
    # admin can also fetch member's task by id (the user_id filter is skipped for admin)
    task_id = created.json()["id"]
    single = await client.get(f"/api/v1/daily-tasks/{task_id}", headers=_auth(admin_token))
    assert single.status_code == 200


@pytest.mark.asyncio
async def test_run_auto_archive(client: AsyncClient, admin_token: str):
    """run_auto_archive 是 lifespan 排程呼叫的純函式，直接以 test db_factory 呼叫。"""
    # create a done daily task 100 days old for the admin user
    old = (date.today() - timedelta(days=100)).isoformat()
    created = await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "auto archive me", "date": old, "status": "done", "labels": []},
        headers=_auth(admin_token),
    )
    assert created.status_code == 201

    engine = create_async_engine(TEST_DB_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # enable auto_archive_days=90 for all users so admin's old task qualifies
    async with engine.begin() as conn:
        await conn.execute(update(User).values(auto_archive_days=90))

    archived = await run_auto_archive(factory)
    await engine.dispose()
    assert archived >= 1


@pytest.mark.asyncio
async def test_run_auto_archive_no_eligible_users(client: AsyncClient, admin_token: str):
    """所有使用者 auto_archive_days=0（預設）→ 封存 0 筆，覆蓋 early-continue 與空結果分支。"""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # default auto_archive_days is 0 -> no users selected
    archived = await run_auto_archive(factory)
    await engine.dispose()
    assert archived == 0
