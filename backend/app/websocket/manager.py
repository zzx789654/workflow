import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # project_id -> {user_id: WebSocket}
        self._connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, websocket: WebSocket, project_id: str, user_id: str) -> None:
        await websocket.accept()
        self._connections[project_id][user_id] = websocket
        await self.broadcast(project_id, {"type": "presence", "user_id": user_id, "action": "joined"}, exclude=user_id)

    def disconnect(self, project_id: str, user_id: str) -> None:
        self._connections[project_id].pop(user_id, None)
        if not self._connections[project_id]:
            del self._connections[project_id]

    async def broadcast(self, project_id: str, data: dict[str, Any], exclude: str | None = None) -> None:
        payload = json.dumps(data, default=str)
        dead: list[str] = []
        for uid, ws in list(self._connections.get(project_id, {}).items()):
            if uid == exclude:
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self._connections[project_id].pop(uid, None)

    def online_users(self, project_id: str) -> list[str]:
        return list(self._connections.get(project_id, {}).keys())


manager = ConnectionManager()
