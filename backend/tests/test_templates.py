import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_templates_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/project-templates/", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_template(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/project-templates/",
        json={
            "name": "Sprint Template",
            "description": "Two week sprint",
            "color": "#abcdef",
            "tasks": [
                {"title": "Plan", "day_offset_start": 0, "day_offset_end": 1},
                {"title": "Build", "day_offset_start": 2, "day_offset_end": 8},
            ],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Sprint Template"
    assert len(data["tasks"]) == 2


@pytest.mark.asyncio
async def test_get_template(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/project-templates/",
        json={"name": "Get Tmpl", "tasks": []},
        headers=_auth(admin_token),
    )
    tid = create.json()["id"]
    resp = await client.get(f"/api/v1/project-templates/{tid}", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["id"] == tid


@pytest.mark.asyncio
async def test_get_template_not_found(client: AsyncClient, admin_token: str):
    fake = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/project-templates/{fake}", headers=_auth(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_template(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/project-templates/",
        json={"name": "Upd Tmpl", "tasks": []},
        headers=_auth(admin_token),
    )
    tid = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/project-templates/{tid}",
        json={"name": "Updated Name"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_replace_template_tasks(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/project-templates/",
        json={"name": "Replace Tmpl", "tasks": [{"title": "Old"}]},
        headers=_auth(admin_token),
    )
    tid = create.json()["id"]
    resp = await client.put(
        f"/api/v1/project-templates/{tid}/tasks",
        json=[{"title": "New A"}, {"title": "New B"}],
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    titles = {t["title"] for t in resp.json()["tasks"]}
    assert titles == {"New A", "New B"}


@pytest.mark.asyncio
async def test_apply_template(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/project-templates/",
        json={
            "name": "Apply Tmpl",
            "tasks": [{"title": "T1", "day_offset_start": 0, "day_offset_end": 2}],
        },
        headers=_auth(admin_token),
    )
    tid = create.json()["id"]
    resp = await client.post(
        f"/api/v1/project-templates/{tid}/apply",
        json={"project_name": "From Template", "start_date": "2026-06-10"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "From Template"


@pytest.mark.asyncio
async def test_delete_template(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/v1/project-templates/",
        json={"name": "Del Tmpl", "tasks": []},
        headers=_auth(admin_token),
    )
    tid = create.json()["id"]
    resp = await client.delete(f"/api/v1/project-templates/{tid}", headers=_auth(admin_token))
    assert resp.status_code == 204
