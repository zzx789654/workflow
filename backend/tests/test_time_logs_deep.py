"""time_logs 補測：start/stop/manual/delete error 分支、report 權限與過濾、非成員 403。"""

import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_non_member_cannot_list_time_logs(client: AsyncClient, project_id: str, task_id: str, member_token: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_start_stop_timer_flow(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs"
    start = await client.post(f"{base}/start", json={"note": "work"}, headers=_auth(admin_token))
    assert start.status_code == 201
    log_id = start.json()["id"]
    # starting again while one is running -> 400
    again = await client.post(f"{base}/start", json={}, headers=_auth(admin_token))
    assert again.status_code == 400
    # stop it
    stop = await client.patch(f"{base}/{log_id}/stop", headers=_auth(admin_token))
    assert stop.status_code == 200
    # stop again -> 400 already stopped
    stop2 = await client.patch(f"{base}/{log_id}/stop", headers=_auth(admin_token))
    assert stop2.status_code == 400


@pytest.mark.asyncio
async def test_stop_timer_not_found(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/{uuid.uuid4()}/stop",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_manual_log_and_delete(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs"
    manual = await client.post(f"{base}/manual", json={"minutes": 30, "note": "n"}, headers=_auth(admin_token))
    assert manual.status_code == 201
    log_id = manual.json()["id"]
    delete = await client.delete(f"{base}/{log_id}", headers=_auth(admin_token))
    assert delete.status_code == 204


@pytest.mark.asyncio
async def test_delete_log_not_found(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs/{uuid.uuid4()}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_other_users_log_forbidden(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, member_user, member_token: str
):
    # add member, member logs time, admin's log stays separate
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs"
    admin_log = await client.post(f"{base}/manual", json={"minutes": 10}, headers=_auth(admin_token))
    log_id = admin_log.json()["id"]
    # member tries to delete admin's log -> 403
    resp = await client.delete(f"{base}/{log_id}", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_time_report_with_project_filter(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs"
    await client.post(f"{base}/manual", json={"minutes": 45}, headers=_auth(admin_token))
    resp = await client.get(f"/api/v1/time-logs/report?project_id={project_id}", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()["report"]) >= 1


@pytest.mark.asyncio
async def test_time_report_non_member_project_forbidden(
    client: AsyncClient, admin_token: str, project_id: str, member_token: str
):
    resp = await client.get(f"/api/v1/time-logs/report?project_id={project_id}", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_time_report_non_admin_no_filter_restricts_to_own(client: AsyncClient, member_token: str):
    # member with no projects -> empty report (visible_ids branch)
    resp = await client.get("/api/v1/time-logs/report", headers=_auth(member_token))
    assert resp.status_code == 200
    assert resp.json()["report"] == []


@pytest.mark.asyncio
async def test_time_report_user_filter(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    me = await client.get("/api/v1/users/me", headers=_auth(admin_token))
    admin_id = me.json()["id"]
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/time-logs"
    await client.post(f"{base}/manual", json={"minutes": 20}, headers=_auth(admin_token))
    resp = await client.get(f"/api/v1/time-logs/report?user_id={admin_id}", headers=_auth(admin_token))
    assert resp.status_code == 200
