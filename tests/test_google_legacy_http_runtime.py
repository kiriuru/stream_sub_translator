from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.core.cache_manager import CacheManager
from backend.core.google_legacy_http_parser import GoogleLegacyHttpParsedResult
from backend.core.subtitle_router import RuntimeOrchestrator
from backend.models import ObsCaptionDiagnostics


class _RecordingWsManager:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def broadcast(self, message: dict) -> None:
        self.messages.append(message)


class _FakeObsCaptionOutput:
    def __init__(self) -> None:
        self.events = []
        self.payloads = []

    async def publish_source_event(self, event) -> None:
        self.events.append(event)

    async def publish_subtitle_payload(self, payload) -> None:
        self.payloads.append(payload)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def apply_live_settings(self, _config: dict) -> None:
        return None

    def diagnostics(self) -> ObsCaptionDiagnostics:
        return ObsCaptionDiagnostics()


class _FakeTranslationDispatcher:
    def __init__(self) -> None:
        self.finals: list[dict] = []

    async def submit_final(self, *, sequence: int, source_text: str, source_lang: str) -> None:
        self.finals.append(
            {
                "sequence": sequence,
                "source_text": source_text,
                "source_lang": source_lang,
            }
        )

    async def stop(self) -> None:
        return None


class GoogleLegacyHttpRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = {
            "source_lang": "auto",
            "asr": {
                "mode": "local",
                "provider_preference": "google_legacy_http_experimental",
                "google_legacy_http": {
                    "enabled": True,
                    "language": "ru-RU",
                    "profanity_filter": False,
                    "connect_timeout_ms": 10000,
                    "send_timeout_ms": 10000,
                    "recv_timeout_ms": 30000,
                    "max_queue_depth": 50,
                    "reconnect_initial_ms": 1000,
                    "reconnect_max_ms": 30000,
                    "endpoint_host": "https://example.test",
                    "pair_id_prefix": "sst",
                },
            },
            "translation": {
                "enabled": True,
                "target_languages": ["en"],
            },
            "subtitle_output": {
                "show_source": True,
                "show_translations": True,
                "max_translation_languages": 1,
                "display_order": ["source", "en"],
            },
            "overlay": {"preset": "stacked", "compact": False},
            "subtitle_style": {},
            "subtitle_lifecycle": {
                "completed_block_ttl_ms": 4500,
                "completed_source_ttl_ms": 4500,
                "completed_translation_ttl_ms": 4500,
                "pause_to_finalize_ms": 350,
                "allow_early_replace_on_next_final": True,
                "sync_source_and_translation_expiry": True,
                "hard_max_phrase_ms": 5500,
            },
        }
        self.ws_manager = _RecordingWsManager()
        self.runtime = RuntimeOrchestrator(
            self.ws_manager,
            config_getter=lambda: self.config,
            cache_manager=CacheManager(self.root / "cache"),
            export_dir=self.root / "exports",
            models_dir=self.root / "models",
            structured_logger=None,
        )
        self.runtime._obs_caption_output = _FakeObsCaptionOutput()  # noqa: SLF001
        self.runtime._translation_dispatcher = _FakeTranslationDispatcher()  # noqa: SLF001
        self.runtime._state = self.runtime._state.model_copy(  # noqa: SLF001
            update={
                "is_running": True,
                "running": True,
                "status": "listening",
                "phase": "listening",
                "started_at_utc": "2026-01-01T00:00:00+00:00",
            }
        )
        self.runtime._device_id = "mic0"  # noqa: SLF001

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_partial_and_final_flow_use_existing_subtitle_router_pipeline(self) -> None:
        await self.runtime._handle_google_legacy_http_result(  # noqa: SLF001
            GoogleLegacyHttpParsedResult(text="privet", is_partial=True, is_final=False, language="ru-RU")
        )
        await self.runtime._handle_google_legacy_http_result(  # noqa: SLF001
            GoogleLegacyHttpParsedResult(text="privet mir", is_partial=False, is_final=True, language="ru-RU")
        )

        transcript_updates = [message for message in self.ws_manager.messages if message.get("type") == "transcript_update"]
        subtitle_updates = [message for message in self.ws_manager.messages if message.get("type") == "subtitle_payload_update"]

        self.assertEqual(len(transcript_updates), 2)
        self.assertEqual(transcript_updates[0]["payload"]["event"], "partial")
        self.assertEqual(transcript_updates[1]["payload"]["event"], "final")
        self.assertTrue(subtitle_updates)
        self.assertEqual(self.runtime._obs_caption_output.events[0].event, "partial")  # noqa: SLF001
        self.assertEqual(self.runtime._obs_caption_output.events[1].event, "final")  # noqa: SLF001
        self.assertEqual(self.runtime._translation_dispatcher.finals[0]["source_text"], "privet mir")  # noqa: SLF001
        self.assertEqual(self.runtime._translation_dispatcher.finals[0]["source_lang"], "ru")  # noqa: SLF001

    async def test_asr_diagnostics_expose_provider_counters_without_api_key(self) -> None:
        diagnostics = self.runtime.asr_diagnostics().model_dump(mode="json")

        self.assertEqual(diagnostics["provider"], "google_legacy_http_experimental")
        self.assertEqual(diagnostics["provider_label"], "Google Legacy HTTP Speech Experimental")
        self.assertIn("provider_state", diagnostics)
        self.assertEqual(diagnostics["endpoint_mode"], "legacy_http")
        self.assertFalse(diagnostics["uses_google_cloud_api"])
        self.assertFalse(diagnostics["requires_api_key"])
        self.assertNotIn("api_key", self.config["asr"]["google_legacy_http"])


if __name__ == "__main__":
    unittest.main()
