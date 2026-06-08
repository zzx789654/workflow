import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_fields_empty(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.get(f"/api/v1/projects/{project_id}/fields", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_field(client: AsyncClient, admin_token: str, project_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "Severity", "field_type": "select", "options": ["low", "high"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Severity"


@pytest.mark.asyncio
async def test_max_fields_limit(client: AsyncClient, admin_token: str, project_id: str):
    for i in range(5):
        r = await client.post(
            f"/api/v1/projects/{project_id}/fields",
            json={"name": f"F{i}", "field_type": "text"},
            headers=_auth(admin_token),
        )
        assert r.status_code == 201
    # 6th should fail
    resp = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "F6", "field_type": "text"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_field(client: AsyncClient, admin_token: str, project_id: str):
    create = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "Temp", "field_type": "number"},
        headers=_auth(admin_token),
    )
    fid = create.json()["id"]
    resp = await client.delete(f"/api/v1/projects/{project_id}/fields/{fid}", headers=_auth(admin_token))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_set_and_get_field_values(client: AsyncClient, admin_token: str, project_id: str, task_id: str):
    field = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "Notes", "field_type": "text"},
        headers=_auth(admin_token),
    )
    fid = field.json()["id"]
    put = await client.put(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/field-values",
        json=[{"field_id": fid, "value": "important"}],
        headers=_auth(admin_token),
    )
    assert put.status_code == 200
    get = await client.get(f"/api/v1/projects/{project_id}/tasks/{task_id}/field-values", headers=_auth(admin_token))
    assert get.status_code == 200
    assert any(v["value"] == "important" for v in get.json())
