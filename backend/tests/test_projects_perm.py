"""Projects 權限與邊界分支補測：非成員 403、非 admin 過濾、角色不足擋關。"""

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_non_member_cannot_get_project(client: AsyncClient, project_id: str, member_token: str):
    resp = await client.get(f"/api/v1/projects/{project_id}", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_member_cannot_list_members(client: AsyncClient, project_id: str, member_token: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/members", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_member_cannot_update_project(client: AsyncClient, project_id: str, member_token: str):
    resp = await client.patch(f"/api/v1/projects/{project_id}", json={"name": "x"}, headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_member_cannot_delete_project(client: AsyncClient, project_id: str, member_token: str):
    resp = await client.delete(f"/api/v1/projects/{project_id}", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_update_project(
    client: AsyncClient, admin_token: str, project_id: str, member_user, member_token: str
):
    # add member as viewer, then viewer tries to update (needs manager) -> 403
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "viewer"},
        headers=_auth(admin_token),
    )
    resp = await client.patch(f"/api/v1/projects/{project_id}", json={"name": "x"}, headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_delete_project(
    client: AsyncClient, admin_token: str, project_id: str, member_user, member_token: str
):
    # member role is below owner -> delete project 403
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    resp = await client.delete(f"/api/v1/projects/{project_id}", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_list_filters_to_own_projects(client: AsyncClient, project_id: str, member_token: str):
    # member is not in the fixture project -> empty list (non-admin branch)
    resp = await client.get("/api/v1/projects/", headers=_auth(member_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_non_admin_overview_filters_to_own_projects(client: AsyncClient, project_id: str, member_token: str):
    resp = await client.get("/api/v1/projects/overview", headers=_auth(member_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_apply_deadline_no_end_date_noop(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    # project has no end_date -> apply-deadline returns 204 without touching tasks
    resp = await client.post(f"/api/v1/projects/{project_id}/apply-deadline", headers=_auth(admin_token))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_add_member_already_exists(client: AsyncClient, admin_token: str, project_id: str, member_user):
    body = {"user_id": member_user.id, "role": "member"}
    await client.post(f"/api/v1/projects/{project_id}/members", json=body, headers=_auth(admin_token))
    resp = await client.post(f"/api/v1/projects/{project_id}/members", json=body, headers=_auth(admin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_own_role_rejected(client: AsyncClient, admin_token: str, project_id: str, admin_user):
    # admin updating own role -> 400 (cannot modify self). admin_user.id needed.
    # fetch admin id via /users/me
    me = await client.get("/api/v1/users/me", headers=_auth(admin_token))
    admin_id = me.json()["id"]
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/members/{admin_id}/role?role=member",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_owner_role_rejected(client: AsyncClient, admin_token: str, project_id: str, member_user):
    # promote member to owner then try to change owner's role -> 400
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "owner"},
        headers=_auth(admin_token),
    )
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/members/{member_user.id}/role?role=member",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_role_member_not_found(client: AsyncClient, admin_token: str, project_id: str, member_user):
    # member exists as user but not a project member -> 404
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/members/{member_user.id}/role?role=member",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient, admin_token: str):
    import uuid

    resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=_auth(admin_token))
    # admin passes membership (treated as owner) but project missing -> 404
    assert resp.status_code == 404
