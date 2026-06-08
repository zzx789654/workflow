import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_archive_project_blocked_by_unfinished_daily(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str
):
    # daily task linked to project task, still pending -> archiving project blocked (409)
    await client.post(
        "/api/v1/daily-tasks/",
        json={"title": "WIP daily", "date": "2026-06-10", "labels": [], "linked_task_id": task_id},
        headers=_auth(admin_token),
    )
    resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"is_archived": True},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_archive_project_moves_done_daily(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # done daily linked to project task -> archiving project succeeds and moves it
    await client.post(
        "/api/v1/daily-tasks/",
        json={
            "title": "Done daily",
            "date": "2026-06-10",
            "labels": [],
            "status": "done",
            "linked_task_id": task_id,
        },
        headers=_auth(admin_token),
    )
    resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"is_archived": True},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_archived"] is True


@pytest.mark.asyncio
async def test_update_project_end_date_propagates(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"end_date": "2026-12-31"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    # task due_date should now be set
    task = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=_auth(admin_token))
    assert task.json()["due_date"] == "2026-12-31"


@pytest.mark.asyncio
async def test_apply_deadline_endpoint(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"end_date": "2026-11-30"},
        headers=_auth(admin_token),
    )
    resp = await client.post(f"/api/v1/projects/{project_id}/apply-deadline", headers=_auth(admin_token))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_remove_owner_member_rejected(client: AsyncClient, admin_token: str, project_id: str):
    # the creator is owner; find owner member id and try to remove -> 400
    members = (await client.get(f"/api/v1/projects/{project_id}/members", headers=_auth(admin_token))).json()
    owner = next(m for m in members if m["role"] == "owner")
    resp = await client.delete(
        f"/api/v1/projects/{project_id}/members/{owner['user']['id']}", headers=_auth(admin_token)
    )
    assert resp.status_code == 400
