"""milestones 補測：任務完成自動記錄 + 關聯日常任務工時加總、update/delete 404。"""

import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_milestone_log_created_on_task_done_with_daily_minutes(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str
):
    # create a done daily task linked to the project task to exercise the
    # daily-minutes aggregation branch in list_milestone_logs
    await client.post(
        "/api/v1/daily-tasks/",
        json={
            "title": "linked work",
            "date": "2026-06-10",
            "status": "done",
            "work_minutes": 90,
            "labels": [],
            "linked_task_id": task_id,
        },
        headers=_auth(admin_token),
    )
    # move task to done -> record_task_completion creates a MilestoneLog
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"status": "done"},
        headers=_auth(admin_token),
    )
    resp = await client.get(f"/api/v1/projects/{project_id}/milestones/", headers=_auth(admin_token))
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    log = logs[0]
    # daily-task aggregation populated
    assert log["daily_task_minutes"] == 90
    assert len(log["daily_tasks"]) == 1


@pytest.mark.asyncio
async def test_update_and_delete_milestone_log(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"status": "done"},
        headers=_auth(admin_token),
    )
    logs = (await client.get(f"/api/v1/projects/{project_id}/milestones/", headers=_auth(admin_token))).json()
    log_id = logs[0]["id"]
    # update note
    upd = await client.patch(
        f"/api/v1/projects/{project_id}/milestones/{log_id}",
        json={"note": "great work"},
        headers=_auth(admin_token),
    )
    assert upd.status_code == 200
    assert upd.json()["note"] == "great work"
    # delete
    rm = await client.delete(f"/api/v1/projects/{project_id}/milestones/{log_id}", headers=_auth(admin_token))
    assert rm.status_code == 204


@pytest.mark.asyncio
async def test_update_milestone_log_not_found(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/milestones/{uuid.uuid4()}",
        json={"note": "x"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_milestone_log_not_found(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.delete(
        f"/api/v1/projects/{project_id}/milestones/{uuid.uuid4()}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404
