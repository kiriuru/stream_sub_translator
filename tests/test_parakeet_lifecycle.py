from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.core.cache_manager import CacheManager
from backend.core.parakeet_provider import BaseOfficialEuParakeetNemoProvider, AsrResult, AsrSegmentResult
from backend.core.subtitle_router import RuntimeOrchestrator
from backend.core.segment_queue import AsrWorkItem
from backend.models import ObsCaptionDiagnostics, RuntimeMetrics, RuntimeState, TranscriptEvent, TranscriptSegment


class _RecordingWsManager:
    async def broadcast(self, message: dict) -> None:
        return None


class _FakeObsCaptionOutput:
    async def publish_source_event(self, _event) -> None:
        return None

    async def publish_subtitle_payload(self, _payload) -> None:
        return None

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
        self.finals: list[str] = []

    async def submit_final(self, *, sequence: int, source_text: str, source_lang: str) -> None:
        self.finals.append(f"{sequence}:{source_text}:{source_lang}")

    async def stop(self) -> None:
        return None


class _FakeSubtitleRouter:
    def __init__(self) -> None:
        self.events: list[TranscriptEvent] = []

    async def handle_transcript(self, event: TranscriptEvent) -> None:
        self.events.append(event)

    def diagnostic_counters(self) -> dict[str, int]:
        return {}


class _FakeProvider:
    def __init__(self) -> None:
        self.inference_mode_enabled = True


class ParakeetLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.runtime = RuntimeOrchestrator(
            _RecordingWsManager(),
            config_getter=lambda: {
                "source_lang": "ru",
                "asr": {
                    "mode": "local",
                    "provider_preference": "official_eu_parakeet_low_latency",
                    "prefer_gpu": False,
                    "realtime": {},
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
                    "hard_max_phrase_ms": 5500,
                },
                "overlay": {"preset": "single", "compact": False},
                "remote": {"enabled": False, "role": "disabled"},
            },
            cache_manager=CacheManager(self.root / "cache"),
            export_dir=self.root / "exports",
            models_dir=self.root / "models",
            structured_logger=None,
        )
        self.runtime._obs_caption_output = _FakeObsCaptionOutput()  # noqa: SLF001
        self.runtime._translation = mock.Mock(submit_final=self._noop_async)  # noqa: SLF001
        self.runtime.subtitle_router = _FakeSubtitleRouter()  # type: ignore[assignment]
        self.runtime._state = RuntimeState(  # noqa: SLF001
            is_running=True,
            running=True,
            status="listening",
            phase="listening",
            started_at_utc="2026-01-01T00:00:00+00:00",
            metrics=RuntimeMetrics(),
        )
        self.runtime._device_id = "mic0"  # noqa: SLF001
        self.runtime._asr_engine.provider = _FakeProvider()  # noqa: SLF001
        self.runtime._asr_engine.capabilities = lambda: mock.Mock(provider_name="official_eu_parakeet_low_latency")  # type: ignore[method-assign]  # noqa: SLF001
        self.runtime._should_drop_short_hallucination = lambda **_kwargs: False  # type: ignore[method-assign]  # noqa: SLF001
        self.runtime._broadcast_runtime = self._noop_async  # type: ignore[method-assign]  # noqa: SLF001
        self.runtime._set_runtime_state = self._noop_async  # type: ignore[method-assign]  # noqa: SLF001
        self.runtime._set_listening_if_current = self._noop_async  # type: ignore[method-assign]  # noqa: SLF001
        self.broadcasted_events: list[TranscriptEvent] = []
        self.runtime._broadcast_transcript = self._record_transcript  # type: ignore[method-assign]  # noqa: SLF001

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def _noop_async(self, *_args, **_kwargs) -> None:
        return None

    async def _record_transcript(self, event: TranscriptEvent) -> None:
        self.broadcasted_events.append(event)

    async def test_stale_result_is_ignored_after_generation_change(self) -> None:
        def _slow_run(_audio: bytes, *, is_final: bool, segment_id: str | None = None) -> AsrResult:
            _ = segment_id
            time.sleep(0.05)
            return AsrResult(
                segments=[AsrSegmentResult(text="stale", is_partial=not is_final, is_final=is_final)]
            )

        self.runtime._asr_engine.run = _slow_run  # type: ignore[method-assign]  # noqa: SLF001
        self.runtime._asr_runtime_generation = 1  # noqa: SLF001
        self.runtime._segment_queue.push(AsrWorkItem(kind="partial", audio=b"123", duration_ms=120, generation=1))  # noqa: SLF001

        task = asyncio.create_task(self.runtime._asr_loop())  # noqa: SLF001
        await asyncio.sleep(0.01)
        self.runtime._asr_runtime_generation = 2  # noqa: SLF001
        await asyncio.sleep(0.08)
        self.runtime._state = self.runtime._state.model_copy(update={"is_running": False, "running": False})  # noqa: SLF001
        self.runtime._segment_queue.wake()  # noqa: SLF001
        await asyncio.wait_for(task, timeout=1.0)

        ignored = int(self.runtime._metrics.asr_stale_results_ignored or 0)  # noqa: SLF001
        dropped = int(self.runtime._metrics.stale_partial_jobs_dropped or 0)  # noqa: SLF001
        self.assertEqual(ignored + dropped, 1)
        self.assertEqual(self.broadcasted_events, [])

    async def test_final_equal_to_previous_partial_is_still_emitted(self) -> None:
        calls: list[tuple[bool, str | None]] = []

        def _run(_audio: bytes, *, is_final: bool, segment_id: str | None = None) -> AsrResult:
            calls.append((is_final, segment_id))
            return AsrResult(
                segments=[AsrSegmentResult(text="same", is_partial=not is_final, is_final=is_final)]
            )

        self.runtime._asr_engine.run = _run  # type: ignore[method-assign]  # noqa: SLF001
        self.runtime._asr_runtime_generation = 3  # noqa: SLF001
        now = time.perf_counter()
        self.runtime._segment_queue.push(  # noqa: SLF001
            AsrWorkItem(kind="partial", audio=b"p", duration_ms=100, generation=3, segment_id="seg-1", created_at_monotonic=now)
        )

        task = asyncio.create_task(self.runtime._asr_loop())  # noqa: SLF001
        for _ in range(20):
            if len(self.broadcasted_events) >= 1:
                break
            await asyncio.sleep(0.01)
        self.runtime._segment_queue.push(  # noqa: SLF001
            AsrWorkItem(kind="final", audio=b"f", duration_ms=120, generation=3, segment_id="seg-1", created_at_monotonic=now)
        )
        for _ in range(20):
            if len(self.broadcasted_events) >= 2:
                break
            await asyncio.sleep(0.01)
        self.runtime._state = self.runtime._state.model_copy(update={"is_running": False, "running": False})  # noqa: SLF001
        self.runtime._segment_queue.wake()  # noqa: SLF001
        await asyncio.wait_for(task, timeout=1.0)

        self.assertEqual([event.event for event in self.broadcasted_events], ["partial", "final"])
        self.assertEqual([event.text for event in self.broadcasted_events], ["same", "same"])
        self.assertEqual(calls, [(False, "seg-1"), (True, "seg-1")])

    def test_inference_mode_helper_prefers_torch_inference_mode(self) -> None:
        provider = BaseOfficialEuParakeetNemoProvider(self.root / "models", prefer_gpu=False)

        class _FakeInferenceContext:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        class _FakeTorchModule:
            @staticmethod
            def inference_mode():
                return _FakeInferenceContext()

        with mock.patch("backend.core.parakeet_provider.importlib.import_module", return_value=_FakeTorchModule()):
            context = provider._torch_inference_context()  # noqa: SLF001
            with context:
                pass

        self.assertTrue(provider.inference_mode_enabled)


if __name__ == "__main__":
    unittest.main()
