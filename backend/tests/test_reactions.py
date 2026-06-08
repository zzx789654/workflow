import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_reactions_empty(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, comment_id: str
):
    resp = await client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions/",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_toggle_reaction_add(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, comment_id: str
):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions/toggle",
        json={"emoji": "👍"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "added"
    assert "👍" in resp.json()["summary"]


@pytest.mark.asyncio
async def test_toggle_reaction_remove(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, comment_id: str
):
    url = f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions/toggle"
    await client.post(url, json={"emoji": "🎉"}, headers=_auth(admin_token))
    resp = await client.post(url, json={"emoji": "🎉"}, headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["action"] == "removed"


@pytest.mark.asyncio
async def test_toggle_reaction_invalid_emoji(
    client: AsyncClient, admin_token: str, project_id: str, task_id: str, comment_id: str
):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions/toggle",
        json={"emoji": "🦄"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400
