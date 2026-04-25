from __future__ import annotations

import json
import time
from typing import Any

from backend.models import SubtitlePayloadEvent
from backend.ws_manager import WebSocketManager


class OverlayBroadcaster:
    def __init__(self, ws_manager: WebSocketManager) -> None:
        self.ws_manager = ws_manager
        self._last_payload_signature: str | None = None
        self._last_publish_monotonic: float = 0.0

    async def publish(self, payload: dict[str, Any] | SubtitlePayloadEvent) -> None:
        body = payload.model_dump() if isinstance(payload, SubtitlePayloadEvent) else payload
        payload_signature = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        now_monotonic = time.perf_counter()
        if (
            self._last_payload_signature == payload_signature
            and (now_monotonic - self._last_publish_monotonic) < 1.0
        ):
            return
        self._last_payload_signature = payload_signature
        self._last_publish_monotonic = now_monotonic
        await self.ws_manager.broadcast({"type": "overlay_update", "payload": body})
