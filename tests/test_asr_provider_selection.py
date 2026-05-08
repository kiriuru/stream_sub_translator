from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.core.cache_manager import CacheManager
from backend.core.parakeet_provider import AsrProviderDiagnostics, AsrProviderStatus
from backend.core.runtime_orchestrator import RuntimeOrchestrator
from backend.models import ObsCaptionDiagnostics


def _removed_provider_value() -> str:
    return "_".join(["google", "legacy", "http", "experimental"])


class _RecordingWsManager:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def broadcast(self, message: dict) -> None:
        self.messages.append(message)


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
    created: list["_FakeAudioCapture"] = []

    def __init__(self) -> None:
        self.started_with: list[str | None] = []
        self.stopped = 0
        self.sample_rate = 16000
        _FakeAudioCapture.created.append(self)

    def start(self, device_id: str | None = None) -> None:
        self.started_with.append(device_id)

    def stop(self) -> None:
        self.stopped += 1


def _config(mode: str, provider_preference: str = "official_eu_parakeet_low_latency") -> dict:
    return {
        "source_lang": "auto",
        "asr": {
            "mode": mode,
            "provider_preference": provider_preference,
            "prefer_gpu": False,
            "browser": {
                "recognition_language": "ru-RU",
                "interim_results": True,
                "continuous_results": True,
                "force_finalization_enabled": True,
                "force_finalization_timeout_ms": 1600,
                "experimental": {
                    "start_with_audio_track": True,
                    "fallback_to_default_start": True,
                    "keep_stream_alive": True,
                    "audio_track_constraints": {
                        "echoCancellation": False,
                        "noiseSuppression": False,
                        "autoGainControl": False,
                    },
                },
            },
            "realtime": {
                "vad_mode": 3,
                "energy_gate_enabled": False,
                "min_rms_for_recognition": 0.0018,
                "min_voiced_ratio": 0.0,
                "first_partial_min_speech_ms": 180,
                "partial_emit_interval_ms": 450,
                "min_speech_ms": 180,
                "max_segment_ms": 5500,
                "silence_hold_ms": 180,
                "finalization_hold_ms": 350,
                "chunk_window_ms": 0,
                "chunk_overlap_ms": 0,
                "partial_min_delta_chars": 4,
                "partial_coalescing_ms": 160,
            },
        },
        "translation": {"enabled": False, "target_languages": []},
        "subtitle_output": {"show_source": True, "show_translations": False, "display_order": ["source"]},
        "subtitle_style": {},
        "subtitle_lifecycle": {
            "completed_block_ttl_ms": 4500,
            "completed_source_ttl_ms": 4500,
            "completed_translation_ttl_ms": 4500,
            "pause_to_finalize_ms": 350,
            "allow_early_replace_on_next_final": True,
            "sync_source_and_translation_expiry": True,
            "keep_completed_translation_during_active_partial": True,
            "hard_max_phrase_ms": 5500,
        },
        "overlay": {"preset": "single", "compact": False},
        "remote": {"enabled": False, "role": "disabled"},
    }


class AsrProviderSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        _FakeAudioCapture.created.clear()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    def _build_runtime(self, config: dict) -> RuntimeOrchestrator:
        runtime = RuntimeOrchestrator(
            _RecordingWsManager(),
            config_getter=lambda: config,
            cache_manager=CacheManager(self.root / "cache"),
            export_dir=self.root / "exports",
            models_dir=self.root / "models",
            structured_logger=None,
        )
        runtime._obs_caption_output = _FakeObsCaptionOutput()  # noqa: SLF001

        async def _noop_loop() -> None:
            return None

        runtime._capture_loop = _noop_loop  # type: ignore[method-assign]
        runtime._asr_loop = _noop_loop  # type: ignore[method-assign]
        return runtime

    async def test_browser_google_uses_browser_worker_path_only(self) -> None:
        config = _config("browser_google")
        runtime = self._build_runtime(config)

        with mock.patch("backend.core.runtime_orchestrator.AudioCapture", _FakeAudioCapture), mock.patch.object(
            runtime._asr_engine,  # noqa: SLF001
            "initialize_runtime",
            side_effect=AssertionError("Parakeet must not initialize for browser_google"),
        ):
            state = await runtime.start(has_audio_inputs=True, device_id="mic0")

        self.assertTrue(state.is_running)
        self.assertEqual(state.asr.provider, "browser_google")
        self.assertFalse(_FakeAudioCapture.created)
        self.assertIsNone(runtime._asr_task)  # noqa: SLF001
        await runtime.stop()

    async def test_browser_google_experimental_uses_experimental_browser_worker_only(self) -> None:
        config = _config("browser_google_experimental")
        runtime = self._build_runtime(config)

        with mock.patch("backend.core.runtime_orchestrator.AudioCapture", _FakeAudioCapture), mock.patch.object(
            runtime._asr_engine,  # noqa: SLF001
            "initialize_runtime",
            side_effect=AssertionError("Parakeet must not initialize for browser_google_experimental"),
        ):
            state = await runtime.start(has_audio_inputs=True, device_id="mic0")

        self.assertTrue(state.is_running)
        self.assertEqual(state.asr.provider, "browser_google_experimental")
        self.assertFalse(_FakeAudioCapture.created)
        self.assertIsNone(runtime._asr_task)  # noqa: SLF001
        await runtime.stop()

    async def test_removed_provider_preference_falls_back_to_parakeet(self) -> None:
        config = _config("local", _removed_provider_value())
        runtime = self._build_runtime(config)
        init_calls = 0

        def _initialize_runtime() -> AsrProviderStatus:
            nonlocal init_calls
            init_calls += 1
            return AsrProviderStatus(
                provider="official_eu_parakeet_low_latency",
                ready=True,
                message="ready",
                partials_supported=True,
                supports_partials=True,
                supports_streaming=True,
                selected_device="cpu",
                selected_execution_provider="nemo_direct",
                runtime_initialized=True,
            )

        def _diagnostics() -> AsrProviderDiagnostics:
            return AsrProviderDiagnostics(
                provider_name="official_eu_parakeet_low_latency",
                supports_gpu=True,
                supports_partials=True,
                supports_streaming=True,
                gpu_requested=False,
                gpu_available=False,
                actual_selected_device="cpu",
                actual_execution_provider="nemo_direct",
                ready=True,
                message="ready",
                runtime_initialized=True,
            )

        with mock.patch("backend.core.runtime_orchestrator.AudioCapture", _FakeAudioCapture), mock.patch.object(
            runtime._asr_engine, "initialize_runtime", side_effect=_initialize_runtime  # noqa: SLF001
        ), mock.patch.object(runtime._asr_engine, "diagnostics", side_effect=_diagnostics):  # noqa: SLF001
            state = await runtime.start(has_audio_inputs=True, device_id="mic0")

        self.assertTrue(state.is_running)
        self.assertEqual(state.asr.provider, "official_eu_parakeet_low_latency")
        self.assertEqual(init_calls, 1)
        self.assertEqual(len(_FakeAudioCapture.created), 1)
        self.assertIsNotNone(runtime._asr_task)  # noqa: SLF001
        await runtime.stop()

    async def test_local_parakeet_selected_without_browser_worker(self) -> None:
        config = _config("local", "official_eu_parakeet")
        runtime = self._build_runtime(config)
        init_calls = 0

        def _initialize_runtime() -> AsrProviderStatus:
            nonlocal init_calls
            init_calls += 1
            return AsrProviderStatus(
                provider="official_eu_parakeet",
                ready=True,
                message="ready",
                partials_supported=False,
                supports_partials=False,
                supports_streaming=False,
                selected_device="cpu",
                selected_execution_provider="nemo_baseline",
                runtime_initialized=True,
            )

        def _diagnostics() -> AsrProviderDiagnostics:
            return AsrProviderDiagnostics(
                provider_name="official_eu_parakeet",
                supports_gpu=True,
                supports_partials=False,
                supports_streaming=False,
                gpu_requested=False,
                gpu_available=False,
                actual_selected_device="cpu",
                actual_execution_provider="nemo_baseline",
                ready=True,
                message="ready",
                runtime_initialized=True,
            )

        with mock.patch("backend.core.runtime_orchestrator.AudioCapture", _FakeAudioCapture), mock.patch.object(
            runtime._asr_engine, "initialize_runtime", side_effect=_initialize_runtime  # noqa: SLF001
        ), mock.patch.object(runtime._asr_engine, "diagnostics", side_effect=_diagnostics):  # noqa: SLF001
            state = await runtime.start(has_audio_inputs=True, device_id="mic0")

        self.assertTrue(state.is_running)
        self.assertEqual(state.asr.provider, "official_eu_parakeet")
        self.assertEqual(init_calls, 1)
        self.assertEqual(len(_FakeAudioCapture.created), 1)
        self.assertIsNotNone(runtime._asr_task)  # noqa: SLF001
        await runtime.stop()


if __name__ == "__main__":
    unittest.main()
