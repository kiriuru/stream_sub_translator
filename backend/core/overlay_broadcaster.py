from __future__ import annotations

from typing import Any

from backend.models import SubtitlePayloadEvent
from backend.ws_manager import WebSocketManager


class OverlayBroadcaster:
    def __init__(self, ws_manager: WebSocketManager) -> None:
        self.ws_manager = ws_manager

    async def publish(self, payload: dict[str, Any] | SubtitlePayloadEvent) -> None:
        body = payload.model_dump() if isinstance(payload, SubtitlePayloadEvent) else payload
        await self.ws_manager.broadcast({"type": "overlay_update", "payload": body})
