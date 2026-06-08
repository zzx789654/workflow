import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_overview(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get("/api/v1/projects/overview", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(p["id"] == project_id for p in data)


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["id"] == project_id


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Renamed", "description": "new desc"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


@pytest.mark.asyncio
async def test_archive_project(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"is_archived": True},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_archived"] is True


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.delete(f"/api/v1/projects/{project_id}", headers=_auth(admin_token))
    assert resp.status_code == 204
    get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=_auth(admin_token))
    assert get_resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/members", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_add_and_remove_member(client: AsyncClient, admin_token: str, project_id: str, member_user):
    add = await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    assert add.status_code == 201
    assert add.json()["role"] == "member"

    # duplicate add -> 400
    dup = await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    assert dup.status_code == 400

    remove = await client.delete(f"/api/v1/projects/{project_id}/members/{member_user.id}", headers=_auth(admin_token))
    assert remove.status_code == 204


@pytest.mark.asyncio
async def test_update_member_role(client: AsyncClient, admin_token: str, project_id: str, member_user):
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/members/{member_user.id}/role?role=manager",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "manager"


@pytest.mark.asyncio
async def test_remove_member_not_found(client: AsyncClient, admin_token: str, project_id: str):
    fake = str(uuid.uuid4())
    resp = await client.delete(f"/api/v1/projects/{project_id}/members/{fake}", headers=_auth(admin_token))
    assert resp.status_code == 404
