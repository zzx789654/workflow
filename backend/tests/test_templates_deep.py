"""Templates 深度補測：apply 依賴接線/工作日排程、from-project、權限 403、404。"""

import uuid

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _make_template(client, token, tasks):
    resp = await client.post(
        "/api/v1/project-templates/",
        json={"name": "T", "color": "#abcdef", "tasks": tasks},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_apply_template_with_dependencies_and_dates(client: AsyncClient, admin_token: str):
    # two tasks, second depends on first, with multi-day offsets -> exercises
    # workday scheduling + dependency wiring branches
    tmpl = await _make_template(
        client,
        admin_token,
        [
            {"title": "T1", "priority": "high", "day_offset_start": 0, "day_offset_end": 2},
            {"title": "T2", "priority": "urgent", "day_offset_start": 0, "day_offset_end": 0, "depends_on_position": 0},
        ],
    )
    resp = await client.post(
        f"/api/v1/project-templates/{tmpl['id']}/apply",
        json={"project_name": "P", "start_date": "2026-06-13", "end_date": "2026-07-13"},  # 2026-06-13 is Sat
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]
    # tasks were created in the new project
    tasks = await client.get(f"/api/v1/projects/{project_id}/tasks/", headers=_auth(admin_token))
    assert tasks.status_code == 200
    assert len(tasks.json()) == 2


@pytest.mark.asyncio
async def test_apply_template_no_start_date_uses_today(client: AsyncClient, admin_token: str):
    tmpl = await _make_template(
        client, admin_token, [{"title": "A", "priority": "low", "day_offset_start": 0, "day_offset_end": 0}]
    )
    resp = await client.post(
        f"/api/v1/project-templates/{tmpl['id']}/apply",
        json={"project_name": "NoStart"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_apply_template_not_found(client: AsyncClient, admin_token: str):
    resp = await client.post(
        f"/api/v1/project-templates/{uuid.uuid4()}/apply",
        json={"project_name": "X"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_template_from_project(client: AsyncClient, admin_token: str, project_id: str):
    # add tasks with and without dates to the project
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Dated", "start_date": "2026-06-10", "end_date": "2026-06-12"},
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "NoDates"},
        headers=_auth(admin_token),
    )
    resp = await client.post(
        f"/api/v1/project-templates/from-project/{project_id}?name=FromProj",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "FromProj"
    assert len(resp.json()["tasks"]) >= 2


@pytest.mark.asyncio
async def test_create_template_from_project_not_found(client: AsyncClient, admin_token: str):
    resp = await client.post(
        f"/api/v1/project-templates/from-project/{uuid.uuid4()}?name=X",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_template_forbidden_for_non_owner(client: AsyncClient, admin_token: str, member_token: str):
    tmpl = await _make_template(client, admin_token, [])
    resp = await client.patch(
        f"/api/v1/project-templates/{tmpl['id']}",
        json={"name": "hacked"},
        headers=_auth(member_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_template_forbidden_for_non_owner(client: AsyncClient, admin_token: str, member_token: str):
    tmpl = await _make_template(client, admin_token, [])
    resp = await client.delete(f"/api/v1/project-templates/{tmpl['id']}", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_replace_tasks_forbidden_for_non_owner(client: AsyncClient, admin_token: str, member_token: str):
    tmpl = await _make_template(client, admin_token, [])
    resp = await client.put(
        f"/api/v1/project-templates/{tmpl['id']}/tasks",
        json=[{"title": "X", "priority": "low", "day_offset_start": 0, "day_offset_end": 0}],
        headers=_auth(member_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_template_not_found(client: AsyncClient, admin_token: str):
    resp = await client.patch(
        f"/api/v1/project-templates/{uuid.uuid4()}",
        json={"name": "x"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_member_can_replace_own_template_tasks(client: AsyncClient, member_token: str):
    # owner (member) replaces own template tasks -> 200, exercises happy path of PUT
    tmpl = await _make_template(
        client, member_token, [{"title": "old", "priority": "low", "day_offset_start": 0, "day_offset_end": 0}]
    )
    resp = await client.put(
        f"/api/v1/project-templates/{tmpl['id']}/tasks",
        json=[{"title": "new", "priority": "high", "day_offset_start": 0, "day_offset_end": 1}],
        headers=_auth(member_token),
    )
    assert resp.status_code == 200
    assert resp.json()["tasks"][0]["title"] == "new"
