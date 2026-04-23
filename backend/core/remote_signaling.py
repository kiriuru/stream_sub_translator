from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class RemoteSignalingManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, *, session_id: str, role: str, websocket: WebSocket) -> None:
        await websocket.accept()
        stale: WebSocket | None = None
        async with self._lock:
            session = self._sessions.setdefault(session_id, {})
            stale = session.get(role)
            session[role] = websocket
        if stale is not None and stale is not websocket:
            try:
                await stale.close(code=1012)
            except Exception:
                pass
        await self._broadcast_peer_state(session_id=session_id)

    async def disconnect(self, *, session_id: str, role: str, websocket: WebSocket) -> None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return
            if session.get(role) is websocket:
                session.pop(role, None)
            if not session:
                self._sessions.pop(session_id, None)
        await self._broadcast_peer_state(session_id=session_id)

    async def relay(self, *, session_id: str, from_role: str, payload: dict[str, Any]) -> bool:
        target_role = "worker" if from_role == "controller" else "controller"
        async with self._lock:
            session = self._sessions.get(session_id, {})
            target = session.get(target_role)
        if target is None:
            return False
        try:
            await target.send_json(
                {
                    "type": "signal",
                    "from_role": from_role,
                    "payload": payload,
                }
            )
            return True
        except Exception:
            return False

    async def _broadcast_peer_state(self, *, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.get(session_id, {})
            controller = session.get("controller")
            worker = session.get("worker")
        payload = {
            "type": "peer_state",
            "session_id": session_id,
            "controller_connected": controller is not None,
            "worker_connected": worker is not None,
        }
        await asyncio.gather(
            self._safe_send(controller, payload),
            self._safe_send(worker, payload),
        )

    async def _safe_send(self, websocket: WebSocket | None, payload: dict[str, Any]) -> None:
        if websocket is None:
            return
        try:
            await websocket.send_json(payload)
        except Exception:
            return

