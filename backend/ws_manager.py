from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._last_message_by_type: dict[str, dict[str, Any]] = {}
        self._accepted_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._diagnostics: dict[str, Any] = {
            "ws_events_connections_active": 0,
            "ws_events_broadcast_count": 0,
            "ws_events_send_failures": 0,
            "ws_events_dead_connections_removed": 0,
            "ws_events_last_error_kind": None,
        }

    async def connect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._accepted_connections:
                self._connections.add(websocket)
                self._diagnostics["ws_events_connections_active"] = len(self._connections)
                return
        await websocket.accept()
        async with self._lock:
            self._accepted_connections.add(websocket)
            self._connections.add(websocket)
            self._diagnostics["ws_events_connections_active"] = len(self._connections)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            removed = websocket in self._connections
            self._connections.discard(websocket)
            self._accepted_connections.discard(websocket)
            if removed:
                self._diagnostics["ws_events_dead_connections_removed"] = int(
                    self._diagnostics["ws_events_dead_connections_removed"]
                ) + 1
            self._diagnostics["ws_events_connections_active"] = len(self._connections)

    async def broadcast(self, message: dict[str, Any]) -> None:
        message_type = str(message.get("type", "") or "").strip()
        if message_type:
            self._last_message_by_type[message_type] = message
        async with self._lock:
            connections = list(self._connections)
        self._diagnostics["ws_events_broadcast_count"] = int(self._diagnostics["ws_events_broadcast_count"]) + 1
        stale: list[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError, OSError, ConnectionResetError, BrokenPipeError) as exc:
                self._diagnostics["ws_events_send_failures"] = int(self._diagnostics["ws_events_send_failures"]) + 1
                self._diagnostics["ws_events_last_error_kind"] = type(exc).__name__
                stale.append(connection)
        if stale:
            async with self._lock:
                for connection in stale:
                    self._connections.discard(connection)
                    self._accepted_connections.discard(connection)
                self._diagnostics["ws_events_dead_connections_removed"] = int(
                    self._diagnostics["ws_events_dead_connections_removed"]
                ) + len(stale)
                self._diagnostics["ws_events_connections_active"] = len(self._connections)

    async def replay_last(self, websocket: WebSocket, *, message_types: list[str]) -> None:
        for message_type in message_types:
            cached = self._last_message_by_type.get(str(message_type or "").strip())
            if cached:
                try:
                    await websocket.send_json(cached)
                except (WebSocketDisconnect, RuntimeError, OSError, ConnectionResetError, BrokenPipeError) as exc:
                    self._diagnostics["ws_events_send_failures"] = int(self._diagnostics["ws_events_send_failures"]) + 1
                    self._diagnostics["ws_events_last_error_kind"] = type(exc).__name__
                    await self.disconnect(websocket)
                    return

    def diagnostics(self) -> dict[str, Any]:
        snapshot = dict(self._diagnostics)
        snapshot["ws_events_connections_active"] = len(self._connections)
        snapshot["captured_at_ms"] = int(time.time() * 1000)
        return snapshot

