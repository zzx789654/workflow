import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _make_task(client, token, project_id, title):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": title},
        headers=_auth(token),
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_list_deps_empty(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_dependency(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    other = await _make_task(client, admin_token, project_id, "Other task")
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/",
        json={"to_task_id": other},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["to_task_id"] == other


@pytest.mark.asyncio
async def test_self_dependency_rejected(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/",
        json={"to_task_id": task_id},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cycle_rejected(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    other = await _make_task(client, admin_token, project_id, "B")
    # task -> other
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/",
        json={"to_task_id": other},
        headers=_auth(admin_token),
    )
    # other -> task would create a cycle
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{other}/dependencies/",
        json={"to_task_id": task_id},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_remove_dependency(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    other = await _make_task(client, admin_token, project_id, "C")
    add = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/",
        json={"to_task_id": other},
        headers=_auth(admin_token),
    )
    dep_id = add.json()["id"]
    resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies/{dep_id}", headers=_auth(admin_token)
    )
    assert resp.status_code == 204
