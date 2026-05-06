from __future__ import annotations

import asyncio
import unittest

from backend.core.subtitle_router import RuntimeOrchestrator
from backend.models import RuntimeMetrics, RuntimeState


class _RecordingWsManager:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def broadcast(self, message: dict) -> None:
        self.messages.append(message)


class RuntimeEventCoalescingTests(unittest.TestCase):
    def _make_runtime(self) -> RuntimeOrchestrator:
        runtime = RuntimeOrchestrator.__new__(RuntimeOrchestrator)
        runtime.ws_manager = _RecordingWsManager()
        runtime._state = RuntimeState(is_running=True, running=True, status="listening", phase="listening")
        runtime._metrics = RuntimeMetrics()
        runtime._runtime_event_sequence = 0
        runtime._runtime_event_sequence_by_type = {}
        runtime._last_runtime_status_signature = None
        runtime._last_runtime_status_broadcast_monotonic = 0.0
        runtime._runtime_status_heartbeat_interval_ms = 1000
        return runtime

    def test_duplicate_runtime_status_is_suppressed(self) -> None:
        async def scenario() -> None:
            runtime = self._make_runtime()
            await RuntimeOrchestrator._broadcast_runtime(runtime)
            await RuntimeOrchestrator._broadcast_runtime(runtime)

            self.assertEqual(len(runtime.ws_manager.messages), 1)
            self.assertEqual(runtime._metrics.runtime_status_duplicate_suppressed, 1)

        asyncio.run(scenario())

    def test_important_runtime_state_change_bypasses_throttle(self) -> None:
        async def scenario() -> None:
            runtime = self._make_runtime()
            await RuntimeOrchestrator._broadcast_runtime(runtime)
            runtime._state = RuntimeState(is_running=True, running=True, status="transcribing", phase="transcribing")
            await RuntimeOrchestrator._broadcast_runtime(runtime)

            self.assertEqual(len(runtime.ws_manager.messages), 2)
            self.assertEqual(runtime._metrics.runtime_status_broadcast_count, 2)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
