from __future__ import annotations

import unittest
from unittest import mock

from backend.core.runtime_orchestrator import RuntimeOrchestrator
from backend.models import RuntimeState


class _Ws:
    def diagnostics(self) -> dict:
        return {}

    async def broadcast(self, message: dict) -> None:
        return None


class RuntimeStartAbortTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_reaches_listening_after_session_bumps_generation(self) -> None:
        runtime = RuntimeOrchestrator.__new__(RuntimeOrchestrator)
        runtime._state = RuntimeState()
        runtime._lifecycle = mock.AsyncMock()
        runtime._lifecycle.start = mock.AsyncMock(return_value="2026-05-24T00:00:00+00:00")
        runtime._current_asr_mode = lambda: "local"  # type: ignore[method-assign]
        runtime._current_remote_role = lambda: "disabled"  # type: ignore[method-assign]
        runtime._is_browser_asr_mode = lambda _mode=None: False  # type: ignore[method-assign]
        runtime._uses_remote_audio_source = lambda: False  # type: ignore[method-assign]
        runtime._uses_remote_event_source = lambda: False  # type: ignore[method-assign]
        runtime._build_startup_status_message = lambda: "starting"  # type: ignore[method-assign]
        runtime._browser_worker_state = mock.Mock()
        runtime._audio_capture_ctl = mock.Mock()
        runtime._audio_capture_ctl.capture = mock.Mock()
        runtime._audio_capture_ctl.sample_rate = 16000
        runtime._audio_capture = mock.Mock()
        runtime._asr_runtime_generation = 0
        runtime._runtime_lifecycle_trace = lambda *_a, **_k: None  # type: ignore[method-assign]
        runtime._start_processing_tasks_impl = mock.AsyncMock()  # type: ignore[method-assign]
        runtime._set_runtime_state = mock.AsyncMock(  # type: ignore[method-assign]
            side_effect=lambda **kwargs: setattr(
                runtime,
                "_state",
                runtime._state.model_copy(update=kwargs),
            )
        )

        async def _lifecycle_start() -> str:
            runtime._asr_runtime_generation += 1
            return "2026-05-24T00:00:00+00:00"

        runtime._lifecycle.start.side_effect = _lifecycle_start

        result = await RuntimeOrchestrator.start(runtime, has_audio_inputs=True, device_id="2")

        self.assertEqual(result.status, "listening")
        self.assertTrue(result.is_running)
        runtime._start_processing_tasks_impl.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
