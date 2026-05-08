from __future__ import annotations

import time
from typing import Any, Callable, Literal

from backend.core.runtime.runtime_metrics_collector import (
    enrich_event_payload,
    runtime_material_status_snapshot,
)
from backend.models import RuntimeMetrics, RuntimeState
from backend.ws_manager import WebSocketManager


RuntimeStatus = Literal["idle", "starting", "listening", "transcribing", "translating", "error"]


class RuntimeStateController:
    """
    Stage 1 controller: owns runtime status broadcast coalescing + event sequencing/enrichment.

    It intentionally does NOT own ASR/audio/translation logic. RuntimeOrchestrator still builds RuntimeState
    via the existing builder; this controller is responsible for broadcasting it safely and consistently.
    """

    name = "runtime_state"

    def __init__(
        self,
        ws_manager: WebSocketManager,
        *,
        metrics_getter: Callable[[], RuntimeMetrics],
        metrics_setter: Callable[[RuntimeMetrics], None],
        increment_counter_metric: Callable[[str, int], None],
        heartbeat_interval_ms: int = 1000,
    ) -> None:
        self._ws_manager = ws_manager
        self._metrics_getter = metrics_getter
        self._metrics_setter = metrics_setter
        self._increment_counter_metric = increment_counter_metric
        self._heartbeat_interval_ms = int(heartbeat_interval_ms or 1000)

        self._runtime_event_sequence = 0
        self._runtime_event_sequence_by_type: dict[str, int] = {}
        self._last_runtime_status_signature: tuple[Any, ...] | None = None
        self._last_runtime_status_broadcast_monotonic: float = 0.0

    def reset_broadcast_state(self) -> None:
        self._runtime_event_sequence = 0
        self._runtime_event_sequence_by_type.clear()
        self._last_runtime_status_signature = None
        self._last_runtime_status_broadcast_monotonic = 0.0

    def enrich(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        metrics = self._metrics_getter()
        metrics, self._runtime_event_sequence, enriched = enrich_event_payload(
            metrics,
            payload=payload,
            event_type=str(event_type or "").strip() or "event",
            runtime_event_sequence=self._runtime_event_sequence,
            runtime_event_sequence_by_type=self._runtime_event_sequence_by_type,
        )
        self._metrics_setter(metrics)
        return enriched

    async def broadcast_runtime(self, state: RuntimeState) -> None:
        payload = state.model_dump()
        signature = runtime_material_status_snapshot(payload)
        now_monotonic = time.perf_counter()
        important_change = signature != self._last_runtime_status_signature
        elapsed_ms = (now_monotonic - self._last_runtime_status_broadcast_monotonic) * 1000.0
        if not important_change and elapsed_ms < self._heartbeat_interval_ms:
            self._increment_counter_metric("runtime_status_duplicate_suppressed", 1)
            self._increment_counter_metric("runtime_events_duplicate_suppressed", 1)
            return
        if important_change:
            self._increment_counter_metric("runtime_status_broadcast_count", 1)
        else:
            self._increment_counter_metric("runtime_status_heartbeat_sent", 1)
        self._last_runtime_status_signature = signature
        self._last_runtime_status_broadcast_monotonic = now_monotonic
        await self._ws_manager.broadcast(
            {
                "type": "runtime_update",
                "payload": self.enrich("runtime_status", payload),
            }
        )

