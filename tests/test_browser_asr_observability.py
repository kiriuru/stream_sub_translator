from __future__ import annotations

import asyncio
from pathlib import Path
import unittest

from backend.core.runtime.browser_asr_operational_fsm import BrowserOperationalPhase
from backend.core.runtime.browser_asr_replay import replay_operational_jsonl
from backend.core.runtime.translation_preview_lineage import TranslationPreviewLineage
from backend.core.translation_dispatcher import TranslationDispatcher
from backend.ws_manager import WebSocketManager

from tests.test_translation_dispatcher import _RecordingStructuredLogger, _StubTranslationEngine

_REPO_TESTS = Path(__file__).resolve().parent


class TranslationPreviewLineageTests(unittest.TestCase):
    def test_lineage_key_requires_segment_and_revision(self) -> None:
        self.assertIsNone(TranslationPreviewLineage.lineage_key(None, 1))
        self.assertIsNone(TranslationPreviewLineage.lineage_key("s", None))
        self.assertEqual(TranslationPreviewLineage.lineage_key("s", 3), "s:3")

    def test_supersede_monotonic_per_key(self) -> None:
        ln = TranslationPreviewLineage()
        self.assertEqual(ln.supersede("a"), 1)
        self.assertEqual(ln.supersede("a"), 2)
        self.assertEqual(ln.supersede("b"), 1)


class BrowserAsrReplayTests(unittest.TestCase):
    def test_replay_jsonl_fixture_fsm_and_ingress_rejects(self) -> None:
        path = _REPO_TESTS / "fixtures" / "browser_asr_replay_min.jsonl"
        out = replay_operational_jsonl(path)
        self.assertEqual(out["fsm_phase"], BrowserOperationalPhase.INGEST_PARTIAL.value)
        self.assertEqual(out["ingress_rejects"], 1)


class _SlowFakeWebSocket:
    def __init__(self) -> None:
        self.accepted = 0
        self.messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted += 1

    async def send_json(self, message: dict) -> None:
        await asyncio.sleep(0.02)
        self.messages.append(dict(message))


class WebSocketBoundedQueueTests(unittest.TestCase):
    def test_broadcast_drops_oldest_when_client_lags(self) -> None:
        async def scenario() -> None:
            manager = WebSocketManager(outbound_queue_max=2)
            sock = _SlowFakeWebSocket()
            await manager.connect(sock)
            for index in range(40):
                await manager.broadcast({"type": "evt", "n": index})
            await asyncio.sleep(0.8)
            diag = manager.diagnostics()
            self.assertGreater(int(diag.get("ws_events_dropped_oldest") or 0), 0)
            await manager.disconnect(sock)

        asyncio.run(scenario())

    def test_replay_last_bypasses_queue(self) -> None:
        async def scenario() -> None:
            manager = WebSocketManager(outbound_queue_max=2)
            sock = _SlowFakeWebSocket()
            await manager.connect(sock)
            await manager.broadcast({"type": "runtime_update", "payload": {"x": 1}})
            for index in range(10):
                await manager.broadcast({"type": "noise", "n": index})
            await manager.replay_last(sock, message_types=["runtime_update"])
            names = [m.get("type") for m in sock.messages]
            self.assertIn("runtime_update", names)
            await manager.disconnect(sock)

        asyncio.run(scenario())


class TranslationPreviewSupersessionAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_supersedes_mid_flight_result(self) -> None:
        config = {
            "translation": {
                "enabled": True,
                "provider": "stub",
                "target_languages": ["en"],
                "lines": [
                    {
                        "slot_id": "translation_1",
                        "enabled": True,
                        "target_lang": "en",
                        "provider": "stub",
                        "label": "EN",
                    }
                ],
                "timeout_ms": 5000,
                "queue_max_size": 8,
                "max_concurrent_jobs": 2,
            }
        }
        relevant: set[int] = {1, 2}
        published = []
        engine = _StubTranslationEngine(delays={"translation_1": 0.15})
        logger = _RecordingStructuredLogger()

        async def publish(event) -> None:
            published.append(event)

        dispatcher = TranslationDispatcher(
            engine,
            lambda: config,
            publish,
            lambda sequence: sequence in relevant,
            None,
            structured_logger=logger,
        )
        key = "seg:1"
        await dispatcher.submit_final(sequence=1, source_text="first", source_lang="en", preview_lineage_key=key)
        await asyncio.sleep(0.01)
        await dispatcher.submit_final(sequence=2, source_text="second", source_lang="en", preview_lineage_key=key)
        await asyncio.sleep(0.5)
        await dispatcher.stop()

        non_complete = [e for e in published if e.translations and not e.is_complete]
        seqs = {e.sequence for e in non_complete}
        self.assertNotIn(1, seqs)
        self.assertIn(2, seqs)


if __name__ == "__main__":
    unittest.main()
