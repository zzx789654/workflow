"""ai_assist._get_claude_suggestions 補測：mock Claude API 成功/解析/fallback。"""

import json
from unittest.mock import MagicMock, patch

import pytest

import app.api.v1.endpoints.ai_assist as ai


def _fake_message(text: str):
    msg = MagicMock()
    block = MagicMock()
    block.text = text
    msg.content = [block]
    return msg


@pytest.mark.asyncio
async def test_claude_suggestions_no_api_key_returns_none():
    with patch.object(ai, "ANTHROPIC_API_KEY", ""):
        result = await ai._get_claude_suggestions([{"title": "A"}])
    assert result is None


@pytest.mark.asyncio
async def test_claude_suggestions_empty_tasks_returns_none():
    with patch.object(ai, "ANTHROPIC_API_KEY", "sk-test"):
        result = await ai._get_claude_suggestions([])
    assert result is None


@pytest.mark.asyncio
async def test_claude_suggestions_happy_path():
    tasks = [
        {"title": "Ship release", "priority": "high", "due_date": "2026-06-10", "status": "todo"},
        {"title": "Write docs", "priority": "low", "due_date": None, "status": "todo"},
    ]
    api_reply = json.dumps([{"title": "Ship release", "reason": "最重要"}])
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_message(api_reply)
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client

    with patch.object(ai, "ANTHROPIC_API_KEY", "sk-test"), patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        result = await ai._get_claude_suggestions(tasks)

    assert result is not None
    assert result[0]["title"] == "Ship release"
    assert result[0]["reason"] == "最重要"
    assert result[0]["model"] == "claude-haiku-4-5"


@pytest.mark.asyncio
async def test_claude_suggestions_unmatched_title_returns_none():
    tasks = [{"title": "Real task", "priority": "low", "due_date": None, "status": "todo"}]
    api_reply = json.dumps([{"title": "Hallucinated", "reason": "x"}])
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_message(api_reply)
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client

    with patch.object(ai, "ANTHROPIC_API_KEY", "sk-test"), patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        result = await ai._get_claude_suggestions(tasks)
    # no title matched -> None
    assert result is None


@pytest.mark.asyncio
async def test_claude_suggestions_api_exception_falls_back_to_none():
    tasks = [{"title": "Task", "priority": "low", "due_date": None, "status": "todo"}]
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("boom")
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client

    with patch.object(ai, "ANTHROPIC_API_KEY", "sk-test"), patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        result = await ai._get_claude_suggestions(tasks)
    assert result is None


@pytest.mark.asyncio
async def test_priority_endpoint_uses_claude_when_enabled(client, admin_token, project_id, member_user):
    """End-to-end: endpoint returns claude model label when API succeeds."""
    # assign a task to admin so suggestion list is non-empty
    me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = me.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Claude Task", "assignee_ids": [admin_id], "due_date": "2026-06-15"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    api_reply = json.dumps([{"title": "Claude Task", "reason": "優先"}])
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_message(api_reply)
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client

    with patch.object(ai, "ANTHROPIC_API_KEY", "sk-test"), patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        resp = await client.get(
            "/api/v1/ai/priority-suggestions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "claude-haiku-4-5"
    assert body["ai_enabled"] is True
