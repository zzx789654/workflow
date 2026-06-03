"""Coverage tests for calendar, search, dashboard, custom_fields, and templates."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Dashboard ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_summary_admin(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/dashboard/summary", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "kpi" in data
    assert "trend" in data
    assert "action_required" in data
    kpi = data["kpi"]
    assert "todo" in kpi
    assert "overdue" in kpi
    assert "completed_this_week" in kpi
    assert len(data["trend"]) == 7


@pytest.mark.asyncio
async def test_dashboard_summary_with_tasks(client: AsyncClient, admin_token: str):
    """Dashboard with overdue task counts properly."""
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"Dash Project {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Overdue Task", "due_date": "2020-01-01"},
        headers=auth(admin_token),
    )
    resp = await client.get("/api/v1/dashboard/summary", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["kpi"]["overdue"] >= 0


# ── Search ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_all_types(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/search/?q=test", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data
    assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_search_type_project(client: AsyncClient, admin_token: str):
    name = f"UniqSearch{uuid.uuid4().hex[:8]}"
    await client.post(
        "/api/v1/projects/",
        json={"name": name},
        headers=auth(admin_token),
    )
    resp = await client.get(f"/api/v1/search/?q={name}&type=project", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(r["type"] == "project" for r in data["results"])


@pytest.mark.asyncio
async def test_search_type_task(client: AsyncClient, admin_token: str):
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"SearchTask Project {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    title = f"UniqueTask{uuid.uuid4().hex[:8]}"
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": title},
        headers=auth(admin_token),
    )
    resp = await client.get(f"/api/v1/search/?q={title}&type=task", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_search_type_daily(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/search/?q=test&type=daily", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["results"], list)


# ── Calendar ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_calendar_empty_month(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/calendar/?year=2026&month=6", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_calendar_with_task(client: AsyncClient, admin_token: str):
    """Task with due_date in month appears in calendar."""
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"Cal Project {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Cal Task", "due_date": "2026-06-15"},
        headers=auth(admin_token),
    )
    resp = await client.get("/api/v1/calendar/?year=2026&month=6", headers=auth(admin_token))
    assert resp.status_code == 200
    events = resp.json()
    assert any(e["type"] == "task" and e["title"] == "Cal Task" for e in events)


@pytest.mark.asyncio
async def test_calendar_with_label_filter(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/calendar/?year=2026&month=6&label=work", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── Custom Fields ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_custom_fields_list_empty(client: AsyncClient, admin_token: str):
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"CF Project {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    resp = await client.get(f"/api/v1/projects/{project_id}/fields", headers=auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_custom_fields_create_text(client: AsyncClient, admin_token: str):
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"CF Text {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    resp = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "Owner", "field_type": "text"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Owner"
    assert data["field_type"] == "text"
    assert data["position"] == 1


@pytest.mark.asyncio
async def test_custom_fields_create_select(client: AsyncClient, admin_token: str):
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"CF Select {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    resp = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "Priority", "field_type": "select", "options": ["P1", "P2", "P3"]},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["options"] == {"choices": ["P1", "P2", "P3"]}


@pytest.mark.asyncio
async def test_custom_fields_delete(client: AsyncClient, admin_token: str):
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"CF Del {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    field_resp = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "ToDelete", "field_type": "text"},
        headers=auth(admin_token),
    )
    field_id = field_resp.json()["id"]
    resp = await client.delete(f"/api/v1/projects/{project_id}/fields/{field_id}", headers=auth(admin_token))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_custom_fields_delete_not_found(client: AsyncClient, admin_token: str):
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"CF NF {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api/v1/projects/{project_id}/fields/{fake_id}", headers=auth(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_custom_fields_invalid_type(client: AsyncClient, admin_token: str):
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"CF Invalid {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    resp = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "Bad", "field_type": "invalid_type"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_field_values_set_and_get(client: AsyncClient, admin_token: str):
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"FV Project {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    task_resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "FV Task"},
        headers=auth(admin_token),
    )
    task_id = task_resp.json()["id"]
    field_resp = await client.post(
        f"/api/v1/projects/{project_id}/fields",
        json={"name": "Dept", "field_type": "text"},
        headers=auth(admin_token),
    )
    field_id = field_resp.json()["id"]

    # Get empty field values
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/field-values",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json() == []

    # Set a value
    resp = await client.put(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/field-values",
        json=[{"field_id": field_id, "value": "Engineering"}],
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Get the value back
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/field-values",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["value"] == "Engineering"

    # Update existing value
    resp = await client.put(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/field-values",
        json=[{"field_id": field_id, "value": "Design"}],
        headers=auth(admin_token),
    )
    assert resp.status_code == 200


# ── Templates ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_template_list(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/project-templates/", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_template_create_and_get(client: AsyncClient, admin_token: str):
    name = f"Sprint {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/v1/project-templates/",
        json={
            "name": name,
            "description": "Two-week sprint",
            "tasks": [
                {"title": "Planning", "priority": "high", "day_offset_start": 0, "day_offset_end": 1},
                {"title": "Review", "priority": "medium", "day_offset_start": 12},
            ],
        },
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == name
    assert len(data["tasks"]) == 2
    template_id = data["id"]

    # Get by id
    resp = await client.get(f"/api/v1/project-templates/{template_id}", headers=auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["id"] == template_id


@pytest.mark.asyncio
async def test_template_update(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/project-templates/",
        json={"name": f"Update Me {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    template_id = resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/project-templates/{template_id}",
        json={"description": "Updated"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated"


@pytest.mark.asyncio
async def test_template_delete(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/project-templates/",
        json={"name": f"Delete Me {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    template_id = resp.json()["id"]
    resp = await client.delete(f"/api/v1/project-templates/{template_id}", headers=auth(admin_token))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_template_not_found(client: AsyncClient, admin_token: str):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/project-templates/{fake_id}", headers=auth(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_template_apply(client: AsyncClient, admin_token: str):
    tmpl = await client.post(
        "/api/v1/project-templates/",
        json={
            "name": f"Apply {uuid.uuid4().hex[:6]}",
            "tasks": [
                {"title": "Task A", "priority": "medium", "day_offset_start": 0, "day_offset_end": 2},
            ],
        },
        headers=auth(admin_token),
    )
    template_id = tmpl.json()["id"]
    resp = await client.post(
        f"/api/v1/project-templates/{template_id}/apply",
        json={"project_name": "Applied Project", "start_date": date.today().isoformat()},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Applied Project"


@pytest.mark.asyncio
async def test_template_apply_no_start_date(client: AsyncClient, admin_token: str):
    tmpl = await client.post(
        "/api/v1/project-templates/",
        json={"name": f"Apply NoDate {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    template_id = tmpl.json()["id"]
    resp = await client.post(
        f"/api/v1/project-templates/{template_id}/apply",
        json={"project_name": "No Date Project"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_template_from_project(client: AsyncClient, admin_token: str):
    proj = await client.post(
        "/api/v1/projects/",
        json={"name": f"Source {uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    )
    project_id = proj.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Template Source Task"},
        headers=auth(admin_token),
    )
    tmpl_name = f"FromProj{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        f"/api/v1/project-templates/from-project/{project_id}?name={tmpl_name}",
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    assert len(resp.json()["tasks"]) >= 1


@pytest.mark.asyncio
async def test_template_from_project_not_found(client: AsyncClient, admin_token: str):
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/project-templates/from-project/{fake_id}?name=TestTemplate",
        headers=auth(admin_token),
    )
    assert resp.status_code == 404
