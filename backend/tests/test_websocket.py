"""websocket manager 單元測 + main.py WS endpoint 連線/斷線成功路徑。"""

import uuid

import pytest
from starlette.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.websocket.manager import ConnectionManager


class _FakeWS:
    """最小 WebSocket 替身，記錄 accept 與送出的文字。"""

    def __init__(self):
        self.accepted = False
        self.sent: list[str] = []
        self.should_fail = False

    async def accept(self):
        self.accepted = True

    async def send_text(self, payload: str):
        if self.should_fail:
            raise RuntimeError("connection dead")
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_manager_connect_broadcast_disconnect():
    mgr = ConnectionManager()
    ws1 = _FakeWS()
    ws2 = _FakeWS()
    await mgr.connect(ws1, "proj", "u1")
    assert ws1.accepted
    assert mgr.online_users("proj") == ["u1"]

    # second user joins -> u1 receives a presence broadcast (u2 excluded)
    await mgr.connect(ws2, "proj", "u2")
    assert set(mgr.online_users("proj")) == {"u1", "u2"}
    assert len(ws1.sent) >= 1  # got u2's join event

    # broadcast to all
    await mgr.broadcast("proj", {"type": "ping"})
    assert any("ping" in s for s in ws1.sent)

    # disconnect u1, then u2 -> project entry removed
    mgr.disconnect("proj", "u1")
    assert mgr.online_users("proj") == ["u2"]
    mgr.disconnect("proj", "u2")
    assert mgr.online_users("proj") == []


@pytest.mark.asyncio
async def test_manager_broadcast_drops_dead_connection():
    mgr = ConnectionManager()
    good = _FakeWS()
    dead = _FakeWS()
    await mgr.connect(good, "p", "g")
    await mgr.connect(dead, "p", "d")
    dead.should_fail = True
    await mgr.broadcast("p", {"type": "x"})
    # dead connection pruned
    assert "d" not in mgr.online_users("p")
    assert "g" in mgr.online_users("p")


def test_ws_endpoint_connect_and_disconnect():
    """以有效 token 連上 /ws/{project_id}，覆蓋 connect→receive→disconnect 成功路徑。"""
    client = TestClient(app)
    token = create_access_token(str(uuid.uuid4()))
    with client.websocket_connect(f"/ws/{uuid.uuid4()}?token={token}") as ws:
        ws.send_text("hello")
    # exiting the context triggers WebSocketDisconnect handling on the server


def test_ws_notifications_connect_and_disconnect():
    client = TestClient(app)
    token = create_access_token(str(uuid.uuid4()))
    with client.websocket_connect(f"/ws/notifications?token={token}") as ws:
        ws.send_text("ping")
