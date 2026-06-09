"""attachments 補測：upload/download/delete happy+error、非成員 403、專案層列檔。"""

import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _file(name="a.txt", content=b"hello", ctype="text/plain"):
    return {"file": (name, content, ctype)}


@pytest.mark.asyncio
async def test_non_member_cannot_list_attachments(
    client: AsyncClient, project_id: str, task_id: str, member_token: str
):
    resp = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_upload_download_delete_flow(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments"
    up = await client.post(base + "/", files=_file(), headers=_auth(admin_token))
    assert up.status_code == 201
    att_id = up.json()["id"]
    # list
    lst = await client.get(base + "/", headers=_auth(admin_token))
    assert any(a["id"] == att_id for a in lst.json())
    # download
    dl = await client.get(f"{base}/{att_id}/download", headers=_auth(admin_token))
    assert dl.status_code == 200
    assert dl.content == b"hello"
    # project-level file listing
    pf = await client.get(f"/api/v1/projects/{project_id}/files/", headers=_auth(admin_token))
    assert pf.status_code == 200
    assert any(f["id"] == att_id for f in pf.json())
    # delete
    rm = await client.delete(f"{base}/{att_id}", headers=_auth(admin_token))
    assert rm.status_code == 204


@pytest.mark.asyncio
async def test_upload_disallowed_type(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments"
    resp = await client.post(
        base + "/", files=_file("x.exe", b"MZ", "application/x-msdownload"), headers=_auth(admin_token)
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_too_large(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments"
    big = b"x" * (10 * 1024 * 1024 + 1)
    resp = await client.post(base + "/", files=_file("big.txt", big, "text/plain"), headers=_auth(admin_token))
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_download_not_found(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/{uuid.uuid4()}/download",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_not_found(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    resp = await client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments/{uuid.uuid4()}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_other_users_attachment_forbidden(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, member_user, member_token: str
):
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_user.id, "role": "member"},
        headers=_auth(admin_token),
    )
    base = f"/api/v1/projects/{project_id}/tasks/{task_id}/attachments"
    up = await client.post(base + "/", files=_file(), headers=_auth(admin_token))
    att_id = up.json()["id"]
    resp = await client.delete(f"{base}/{att_id}", headers=_auth(member_token))
    assert resp.status_code == 403
