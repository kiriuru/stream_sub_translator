from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from backend.services.browser_asr_service import BrowserAsrService


class _FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.messages.append(dict(payload))


class _FakeRuntimeOrchestrator:
    def __init__(self) -> None:
        self.connected = 0
        self.disconnected = 0
        self.status_updates: list[dict] = []
        self.external_updates: list[dict] = []

    async def browser_asr_worker_connected(self) -> None:
        self.connected += 1

    async def browser_asr_worker_disconnected(self) -> None:
        self.disconnected += 1

    async def update_browser_asr_worker_status(self, payload: dict) -> None:
        self.status_updates.append(dict(payload))

    async def ingest_external_asr_update(self, **payload) -> None:
        self.external_updates.append(dict(payload))


class BrowserAsrServiceTests(unittest.TestCase):
    def test_stale_generation_is_ignored(self) -> None:
        async def scenario() -> None:
            app = SimpleNamespace(state=SimpleNamespace(runtime_orchestrator=_FakeRuntimeOrchestrator()))
            service = BrowserAsrService(app)
            websocket = _FakeWebSocket()
            transport_id = await service.register_connection(websocket)
            await service.worker_connected()

            accepted = await service.handle_status(
                transport_id,
                {
                    "type": "browser_asr_status",
                    "session_id": "session-a",
                    "generation_id": 3,
                    "recognition_state": "running",
                },
            )
            stale = await service.handle_external_update(
                transport_id,
                {
                    "type": "external_asr_update",
                    "session_id": "session-a",
                    "generation_id": 2,
                    "partial": "old",
                    "is_final": False,
                },
            )

            self.assertTrue(accepted)
            self.assertFalse(stale)
            self.assertEqual(len(app.state.runtime_orchestrator.external_updates), 0)
            self.assertEqual(service.diagnostics()["browser_stale_events_ignored"], 1)

        asyncio.run(scenario())

    def test_external_update_forwards_client_segment_and_forced_final(self) -> None:
        async def scenario() -> None:
            app = SimpleNamespace(state=SimpleNamespace(runtime_orchestrator=_FakeRuntimeOrchestrator()))
            service = BrowserAsrService(app)
            websocket = _FakeWebSocket()
            transport_id = await service.register_connection(websocket)

            accepted = await service.handle_external_update(
                transport_id,
                {
                    "type": "external_asr_update",
                    "session_id": "session-b",
                    "generation_id": 4,
                    "client_segment_id": "browser-seg-4",
                    "partial": "",
                    "final": "hello world",
                    "is_final": True,
                    "forced_final": True,
                    "mic_track_ready_state": "live",
                    "mic_rms": 0.03,
                },
            )

            self.assertTrue(accepted)
            self.assertEqual(len(app.state.runtime_orchestrator.external_updates), 1)
            forwarded = app.state.runtime_orchestrator.external_updates[0]
            self.assertEqual(forwarded["client_segment_id"], "browser-seg-4")
            self.assertTrue(forwarded["forced_final"])

        asyncio.run(scenario())

    def test_status_snapshot_keeps_cycle_and_media_diagnostics(self) -> None:
        async def scenario() -> None:
            app = SimpleNamespace(state=SimpleNamespace(runtime_orchestrator=_FakeRuntimeOrchestrator()))
            service = BrowserAsrService(app)
            websocket = _FakeWebSocket()
            transport_id = await service.register_connection(websocket)

            accepted = await service.handle_status(
                transport_id,
                {
                    "type": "browser_asr_status",
                    "session_id": "session-cycle",
                    "generation_id": 6,
                    "provider_name": "browser_google_experimental",
                    "recognition_state": "running",
                    "active_recognition": True,
                    "active_media_stream": True,
                    "last_result_index": 11,
                    "browser_session_age_ms": 2500,
                    "browser_cycle_pending": True,
                    "browser_cycle_count": 2,
                    "browser_minimum_reconnect_suppressed_count": 1,
                    "browser_forced_final_on_interruption_count": 1,
                    "get_user_media_count": 3,
                    "get_user_media_last_error": "device busy",
                    "mic_stream_active": True,
                    "media_tracks_stopped_count": 4,
                    "media_track_leak_guard_count": 2,
                },
            )

            self.assertTrue(accepted)
            snapshot = service.diagnostics()
            self.assertEqual(snapshot["provider_name"], "browser_google_experimental")
            self.assertTrue(snapshot["active_recognition"])
            self.assertTrue(snapshot["active_media_stream"])
            self.assertEqual(snapshot["last_result_index"], 11)
            self.assertEqual(snapshot["browser_session_age_ms"], 2500)
            self.assertTrue(snapshot["browser_cycle_pending"])
            self.assertEqual(snapshot["browser_cycle_count"], 2)
            self.assertEqual(snapshot["browser_minimum_reconnect_suppressed_count"], 1)
            self.assertEqual(snapshot["browser_forced_final_on_interruption_count"], 1)
            self.assertEqual(snapshot["get_user_media_count"], 3)
            self.assertEqual(snapshot["get_user_media_last_error"], "device busy")
            self.assertTrue(snapshot["mic_stream_active"])
            self.assertEqual(snapshot["media_tracks_stopped_count"], 4)
            self.assertEqual(snapshot["media_track_leak_guard_count"], 2)

        asyncio.run(scenario())

    def test_worker_connected_calls_orchestrator_hook(self) -> None:
        async def scenario() -> None:
            orchestrator = _FakeRuntimeOrchestrator()
            app = SimpleNamespace(state=SimpleNamespace(runtime_orchestrator=orchestrator))
            service = BrowserAsrService(app)
            await service.register_connection(_FakeWebSocket())
            await service.worker_connected()
            self.assertEqual(orchestrator.connected, 1)

        asyncio.run(scenario())


class RuntimeOrchestratorBrowserWorkerApiTests(unittest.TestCase):
    def test_browser_asr_worker_connected_public_method_exists(self) -> None:
        from backend.core.runtime_orchestrator import RuntimeOrchestrator

        self.assertTrue(callable(getattr(RuntimeOrchestrator, "browser_asr_worker_connected", None)))


if __name__ == "__main__":
    unittest.main()
