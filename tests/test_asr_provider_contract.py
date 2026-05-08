from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.core.asr_provider_selection import resolve_effective_asr_provider
from backend.core.cache_manager import CacheManager
from backend.core.subtitle_router import RuntimeOrchestrator
from backend.models import ObsCaptionDiagnostics


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASR_PANEL_JS = PROJECT_ROOT / "frontend" / "js" / "panels" / "asr-panel.js"


def _removed_provider_value() -> str:
    return "_".join(["google", "legacy", "http", "experimental"])


class _RecordingWsManager:
    async def broadcast(self, message: dict) -> None:
        _ = message
        return None


class _FakeObsCaptionOutput:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def apply_live_settings(self, _config: dict) -> None:
        return None

    async def publish_source_event(self, _event) -> None:
        return None

    async def publish_subtitle_payload(self, _payload) -> None:
        return None

    def diagnostics(self) -> ObsCaptionDiagnostics:
        return ObsCaptionDiagnostics()


class _FakeAudioCapture:
    def __init__(self) -> None:
        self.sample_rate = 16000

    def start(self, device_id: str | None = None) -> None:
        _ = device_id
        return None

    def stop(self) -> None:
        return None


class AsrProviderContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolver_prefers_browser_mode_over_removed_local_provider(self) -> None:
        resolved = resolve_effective_asr_provider(
            {
                "asr": {
                    "mode": "browser_google_experimental",
                    "provider_preference": _removed_provider_value(),
                }
            }
        )

        self.assertEqual(resolved["effective_provider"], "browser_google_experimental")
        self.assertEqual(resolved["provider_kind"], "browser_worker_experimental")
        self.assertTrue(resolved["uses_browser_worker"])
        self.assertFalse(resolved["uses_backend_audio_capture"])

    async def test_resolver_falls_back_to_low_latency_parakeet_for_removed_provider(self) -> None:
        resolved = resolve_effective_asr_provider(
            {
                "asr": {
                    "mode": "local",
                    "provider_preference": _removed_provider_value(),
                }
            }
        )

        self.assertEqual(resolved["effective_provider"], "official_eu_parakeet_low_latency")
        self.assertEqual(resolved["provider_kind"], "local_parakeet")
        self.assertTrue(resolved["uses_backend_audio_capture"])
        self.assertFalse(resolved["uses_browser_worker"])

    async def test_runtime_status_exposes_parakeet_provider_kind(self) -> None:
        config = {
            "source_lang": "auto",
            "asr": {
                "mode": "local",
                "provider_preference": "official_eu_parakeet_low_latency",
            },
            "translation": {"enabled": False, "target_languages": []},
            "subtitle_output": {"show_source": True, "show_translations": False, "display_order": ["source"]},
            "subtitle_style": {},
            "subtitle_lifecycle": {},
            "overlay": {"preset": "single", "compact": False},
            "remote": {"enabled": False, "role": "disabled"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = RuntimeOrchestrator(
                _RecordingWsManager(),
                config_getter=lambda: config,
                cache_manager=CacheManager(Path(temp_dir) / "cache"),
                export_dir=Path(temp_dir) / "exports",
                models_dir=Path(temp_dir) / "models",
                structured_logger=None,
            )
            runtime._obs_caption_output = _FakeObsCaptionOutput()  # noqa: SLF001
            runtime._audio_capture = _FakeAudioCapture()  # noqa: SLF001
            runtime._state = runtime._state.model_copy(update={"is_running": True, "running": True, "status": "listening"})  # noqa: SLF001
            runtime._asr_mode._active_runtime_mode = "local"  # noqa: SLF001
            runtime._asr_mode._active_local_provider_preference = "official_eu_parakeet_low_latency"  # noqa: SLF001

            status = runtime._build_runtime_state(  # noqa: SLF001
                is_running=True,
                status="listening",
                started_at_utc="2026-01-01T00:00:00+00:00",
            )

        self.assertEqual(status.asr.effective_provider, "official_eu_parakeet_low_latency")
        self.assertEqual(status.asr.provider_kind, "local_parakeet")

    def test_frontend_provider_selection_keeps_local_mode_without_removed_provider_flags(self) -> None:
        source = ASR_PANEL_JS.read_text(encoding="utf-8")
        self.assertIn('draft.asr.mode = "local";', source)
        self.assertNotIn("_".join(["google", "legacy", "http"]), source)


if __name__ == "__main__":
    unittest.main()
