from __future__ import annotations

from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._last_message_by_type: dict[str, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        message_type = str(message.get("type", "") or "").strip()
        if message_type:
            self._last_message_by_type[message_type] = message
        stale: list[WebSocket] = []
        for connection in list(self._connections):
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)

    async def replay_last(self, websocket: WebSocket, *, message_types: list[str]) -> None:
        for message_type in message_types:
            cached = self._last_message_by_type.get(str(message_type or "").strip())
            if cached:
                await websocket.send_json(cached)

