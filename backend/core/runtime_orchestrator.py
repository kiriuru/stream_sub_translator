from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any, Callable, Literal

from backend.core.asr_engine import AsrEngine
from backend.core.cache_manager import CacheManager
from backend.core.audio_capture import AudioCapture, RNNoiseRecognitionProcessor
from backend.core.asr_provider_selection import (
    BROWSER_GOOGLE_EXPERIMENTAL_MODE,
    BROWSER_GOOGLE_MODE,
    DEFAULT_PARAKEET_PROVIDER,
    LOCAL_ASR_MODE as RESOLVED_LOCAL_ASR_MODE,
)
from backend.core.browser_asr_gateway import BrowserAsrGateway
from backend.core.exporter import Exporter
from backend.core.obs_caption_output import ObsCaptionOutput
from backend.core.parakeet_provider import AsrProviderStatus, OFFICIAL_EU_PARAKEET_REPO
from backend.core.remote_mode import REMOTE_ROLE_WORKER
from backend.core.runtime.asr_runtime_controller import (
    browser_asr_config,
    browser_asr_source_lang,
    browser_worker_provider_name,
    current_asr_mode,
    current_local_provider_preference,
    current_remote_role,
    is_browser_asr_mode,
    is_remote_enabled,
    resolved_asr_provider,
    uses_remote_audio_source,
    uses_remote_event_source,
)
from backend.core.runtime.audio_runtime_controller import (
    clear_async_queue,
    pcm16_rms_level,
    prepare_recognition_audio,
)
from backend.core.runtime.output_fanout_coordinator import broadcast_event, publish_subtitle_payload
from backend.core.runtime.runtime_metrics_collector import (
    apply_translation_dispatcher_metrics,
    enrich_event_payload,
    increment_counter_metric,
    increment_metric,
    next_event_sequence,
    record_metrics,
    runtime_material_status_snapshot,
)
from backend.core.runtime.runtime_status_builder import build_overlay_runtime_status, build_runtime_state
from backend.core.runtime.translation_runtime_coordinator import summarize_translation_diagnostics
from backend.core.segment_queue import AsrWorkItem, SegmentQueue
from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.subtitle_router import (
    BROWSER_ASR_MODE,
    BROWSER_ASR_MODES,
    EXPERIMENTAL_BROWSER_ASR_MODE,
    LOCAL_ASR_MODE,
    SubtitleRouter,
)
from backend.core.translation_dispatcher import TranslationDispatcher
from backend.core.translation_engine import TranslationEngine
from backend.core.vad import VadEngine
from backend.models import (
    AsrDiagnostics,
    ObsCaptionDiagnostics,
    OverlayRuntimeStatus,
    RuntimeMetrics,
    RuntimeState,
    TranscriptEvent,
    TranscriptSegment,
    TranslationDiagnostics,
    TranslationEvent,
)
from backend.ws_manager import WebSocketManager


class RuntimeOrchestrator:
    _SHORT_HALLUCINATION_TOKENS = {
        "yeah",
        "yeah.",
        "mm-hmm",
        "mm-hmm.",
        "mhm",
        "mhm.",
        "uh-huh",
        "uh-huh.",
        "okay",
        "okay.",
        "ok",
        "ok.",
        "hmm",
        "hmm.",
        "uh",
        "uh.",
        "ah",
        "ah.",
        "yep",
        "yep.",
        "nope",
        "nope.",
    }
    _LEGACY_VAD_SETTINGS = {
        "vad_mode": 2,
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
        "partial_min_delta_chars": 12,
        "partial_coalescing_ms": 160,
    }

    def __init__(
        self,
        ws_manager: WebSocketManager,
        *,
        config_getter: Callable[[], dict],
        cache_manager: CacheManager,
        export_dir: Path,
        models_dir: Path,
        structured_logger: StructuredRuntimeLogger | None = None,
    ) -> None:
        self.ws_manager = ws_manager
        self.config_getter = config_getter
        self._obs_caption_output = ObsCaptionOutput(config_getter)
        self.subtitle_router = SubtitleRouter(
            ws_manager,
            config_getter,
            completed_callback=self._handle_completed_export_record,
            presentation_callback=self._handle_obs_caption_payload,
        )
        self._state = RuntimeState()
        self._audio_capture: AudioCapture | None = None
        self._vad = VadEngine()
        self._segment_queue = SegmentQueue()
        self._runtime_loop: asyncio.AbstractEventLoop | None = None
        self._latest_runtime_status_message: str | None = None
        self._asr_engine = AsrEngine(
            models_dir=models_dir,
            config_getter=config_getter,
            runtime_status_callback=self._emit_asr_runtime_status,
        )
        self._translation_engine = TranslationEngine(cache_manager)
        self._exporter = Exporter(export_dir)
        self._structured_runtime_logger = structured_logger
        self._capture_task: asyncio.Task | None = None
        self._asr_task: asyncio.Task | None = None
        self._remote_audio_queue: asyncio.Queue[bytes] | None = None
        self._device_id: str | None = None
        self._sequence = 0
        self._segment_counter = 0
        self._active_segment_id: str | None = None
        self._active_segment_revision = 0
        self._metrics = RuntimeMetrics()
        self._effective_realtime_settings = dict(self._LEGACY_VAD_SETTINGS)
        self._effective_subtitle_lifecycle_settings = {
            "completed_block_ttl_ms": 4500,
            "completed_source_ttl_ms": 4500,
            "completed_translation_ttl_ms": 4500,
            "pause_to_finalize_ms": self._LEGACY_VAD_SETTINGS["finalization_hold_ms"],
            "allow_early_replace_on_next_final": True,
            "sync_source_and_translation_expiry": True,
            "hard_max_phrase_ms": self._LEGACY_VAD_SETTINGS["max_segment_ms"],
        }
        self._session_id: str | None = None
        self._session_started_at_utc: str | None = None
        self._session_started_at_monotonic: float | None = None
        self._session_export_records: list[dict[str, object]] = []
        self._rnnoise_processor = RNNoiseRecognitionProcessor(sample_rate=self._asr_engine.sample_rate, channels=1)
        self._last_partial_text_by_segment: dict[str, str] = {}
        self._last_partial_emit_monotonic_by_segment: dict[str, float] = {}
        self._external_worker_connected = False
        self._browser_asr_gateway = BrowserAsrGateway(structured_logger=structured_logger)
        self._active_runtime_mode: str | None = None
        self._active_local_provider_preference: str | None = None
        self._remote_audio_connected = False
        self._remote_audio_session_id: str | None = None
        self._remote_audio_last_chunk_monotonic: float | None = None
        self._translation_dispatcher_snapshot: dict[str, Any] = {}
        self._runtime_event_sequence = 0
        self._runtime_event_sequence_by_type: dict[str, int] = {}
        self._last_runtime_status_signature: str | None = None
        self._last_runtime_status_broadcast_monotonic: float = 0.0
        self._runtime_status_heartbeat_interval_ms = 1000
        self._active_browser_worker_session_id: str | None = None
        self._active_browser_worker_generation_id: int = 0
        self._last_browser_worker_status_signature: tuple[Any, ...] | None = None
        self._asr_runtime_generation: int = 0
        self._in_flight_transcribe_count: int = 0
        self._translation_dispatcher = TranslationDispatcher(
            self._translation_engine,
            self.config_getter,
            self._publish_translation_dispatch_event,
            self.subtitle_router.is_sequence_relevant_for_translation,
            self._apply_translation_dispatcher_metrics,
            structured_logger=structured_logger,
        )
        self._apply_vad_tuning()
        self._apply_recognition_processing_settings()
        self._translation_engine.apply_live_settings(self.config_getter().get("translation", {}))

    def _emit_asr_runtime_status(self, message: str) -> None:
        normalized = str(message or "").strip()
        if not normalized:
            return
        if normalized == self._latest_runtime_status_message:
            return
        self._latest_runtime_status_message = normalized
        loop = self._runtime_loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._apply_runtime_status_message(normalized))
        )

    async def _apply_runtime_status_message(self, message: str) -> None:
        if self._state.status not in {"starting", "listening", "transcribing", "translating"}:
            return
        self._state = self._state.model_copy(update={"status_message": message})
        await self._broadcast_runtime()

    def _log_runtime_metric_event(self, event: str, **payload: Any) -> None:
        if self._structured_runtime_logger is None:
            return
        self._structured_runtime_logger.log(
            "runtime_metrics",
            event,
            source="runtime_orchestrator",
            payload=payload or None,
        )

    def _current_asr_mode(self) -> str:
        return current_asr_mode(self._resolved_asr_provider())

    def _is_browser_asr_mode(self, mode: str | None = None) -> bool:
        return is_browser_asr_mode(mode or self._current_asr_mode())

    def _resolved_asr_provider(self) -> dict[str, Any]:
        return resolved_asr_provider(
            config_getter=self.config_getter,
            state_is_running=self._state.is_running,
            active_runtime_mode=self._active_runtime_mode,
            active_local_provider_preference=self._active_local_provider_preference,
        )

    def _current_local_provider_preference(self) -> str:
        return current_local_provider_preference(self._resolved_asr_provider())

    def _browser_asr_config(self) -> dict[str, object]:
        return browser_asr_config(self.config_getter())

    def _browser_asr_source_lang(self) -> str:
        return browser_asr_source_lang(self.config_getter())

    def _browser_worker_provider_name(self) -> str:
        return browser_worker_provider_name(self._current_asr_mode())

    def _current_remote_role(self) -> str:
        return current_remote_role(self.config_getter)

    def _uses_remote_audio_source(self) -> bool:
        return uses_remote_audio_source(
            mode=self._current_asr_mode(),
            remote_role=self._current_remote_role(),
        )

    def _is_remote_enabled(self) -> bool:
        return is_remote_enabled(self.config_getter)

    def _uses_remote_event_source(self) -> bool:
        return uses_remote_event_source(
            mode=self._current_asr_mode(),
            remote_enabled=self._is_remote_enabled(),
            remote_role=self._current_remote_role(),
        )

    async def _broadcast_runtime(self) -> None:
        payload = self._state.model_dump()
        signature = self._runtime_material_status_snapshot(payload)
        now_monotonic = time.perf_counter()
        important_change = signature != self._last_runtime_status_signature
        elapsed_ms = (now_monotonic - self._last_runtime_status_broadcast_monotonic) * 1000.0
        if not important_change and elapsed_ms < self._runtime_status_heartbeat_interval_ms:
            self._increment_counter_metric("runtime_status_duplicate_suppressed", 1)
            self._increment_counter_metric("runtime_events_duplicate_suppressed", 1)
            return
        if important_change:
            self._increment_counter_metric("runtime_status_broadcast_count", 1)
        else:
            self._increment_counter_metric("runtime_status_heartbeat_sent", 1)
        self._last_runtime_status_signature = signature
        self._last_runtime_status_broadcast_monotonic = now_monotonic
        await self.ws_manager.broadcast(
            {
                "type": "runtime_update",
                "payload": self._enrich_event_payload("runtime_status", payload),
            }
        )

    async def _broadcast_transcript(self, event: TranscriptEvent) -> None:
        await broadcast_event(
            self.ws_manager,
            channel="transcript_update",
            payload=self._enrich_event_payload("transcript_update", event.model_dump()),
        )

    async def _broadcast_transcript_segment_event(self, event: TranscriptEvent) -> None:
        await broadcast_event(
            self.ws_manager,
            channel="transcript_segment_event",
            payload=self._enrich_event_payload("transcript_segment_event", event.model_dump()),
        )

    async def _broadcast_translation(self, event: TranslationEvent) -> None:
        await broadcast_event(
            self.ws_manager,
            channel="translation_update",
            payload=self._enrich_event_payload("translation_update", event.model_dump()),
        )

    async def _publish_translation_dispatch_event(self, event: TranslationEvent) -> None:
        await self.subtitle_router.handle_translation(event)
        if self.subtitle_router.is_sequence_relevant_for_presentation(event.sequence):
            await self._broadcast_translation(event)
        await self._broadcast_runtime()

    async def _handle_obs_caption_payload(self, payload: SubtitlePayloadEvent) -> None:
        await publish_subtitle_payload(self._obs_caption_output, payload)

    def _reset_export_session(self) -> None:
        self._session_id = None
        self._session_started_at_utc = None
        self._session_started_at_monotonic = None
        self._session_export_records.clear()

    def _handle_completed_export_record(self, record: dict) -> None:
        finalized_at_monotonic = record.get("finalized_at_monotonic")
        if self._session_started_at_monotonic is None or not isinstance(finalized_at_monotonic, (int, float)):
            return

        end_offset_ms = max(0, int(round((float(finalized_at_monotonic) - self._session_started_at_monotonic) * 1000.0)))
        duration_ms_raw = record.get("duration_ms")
        duration_ms = int(duration_ms_raw) if isinstance(duration_ms_raw, (int, float)) and int(duration_ms_raw) > 0 else None
        start_offset_ms = max(0, end_offset_ms - duration_ms) if duration_ms is not None else max(0, end_offset_ms - 1200)

        export_record = dict(record)
        export_record["session_id"] = self._session_id
        export_record["start_offset_ms"] = start_offset_ms
        export_record["end_offset_ms"] = end_offset_ms
        export_record["duration_ms"] = duration_ms
        sequence = export_record.get("sequence")
        if isinstance(sequence, int):
            for index, existing in enumerate(self._session_export_records):
                if int(existing.get("sequence", -1)) == sequence:
                    self._session_export_records[index] = export_record
                    break
            else:
                self._session_export_records.append(export_record)
            return
        self._session_export_records.append(export_record)

    def _export_session_files(self, *, stopped_at_utc: str) -> list[Path]:
        if not self._session_id or not self._session_started_at_utc or not self._session_export_records:
            return []

        config = self.config_getter()
        translation_config = config.get("translation", {}) if isinstance(config, dict) else {}
        subtitle_output = config.get("subtitle_output", {}) if isinstance(config, dict) else {}
        session_row = {
            "type": "session",
            "session_id": self._session_id,
            "started_at_utc": self._session_started_at_utc,
            "stopped_at_utc": stopped_at_utc,
            "profile": str(config.get("profile", "default")) if isinstance(config, dict) else "default",
            "source_lang": str(config.get("source_lang", "auto")) if isinstance(config, dict) else "auto",
            "translation_enabled": bool(translation_config.get("enabled", False)) if isinstance(translation_config, dict) else False,
            "target_languages": list(translation_config.get("target_languages", [])) if isinstance(translation_config, dict) else [],
            "subtitle_output": dict(subtitle_output) if isinstance(subtitle_output, dict) else {},
            "record_count": len(self._session_export_records),
        }
        base_filename = self._exporter.build_session_basename(
            session_started_at_utc=self._session_started_at_utc,
            session_id=self._session_id,
            profile=session_row["profile"],
        )
        return self._exporter.export_session(
            base_filename=base_filename,
            session_row=session_row,
            records=self._session_export_records,
        )

    async def apply_live_settings(self, config: dict) -> None:
        self._apply_vad_tuning()
        self._apply_recognition_processing_settings()
        self._translation_engine.apply_live_settings(config.get("translation", {}) if isinstance(config, dict) else {})
        await self._obs_caption_output.apply_live_settings(config if isinstance(config, dict) else {})
        await self.subtitle_router.republish_latest()
        self._state = self._build_runtime_state(
            is_running=self._state.is_running,
            status=self._state.status,
            started_at_utc=self._state.started_at_utc,
            last_error=self._state.last_error,
            status_message=self._state.status_message,
        )
        await self._broadcast_runtime()

    def _overlay_runtime_status(self) -> OverlayRuntimeStatus:
        return build_overlay_runtime_status(self.config_getter())

    def _build_runtime_state(
        self,
        *,
        is_running: bool,
        status: Literal["idle", "starting", "listening", "transcribing", "translating", "error"],
        started_at_utc: str | None,
        last_error: str | None = None,
        status_message: str | None = None,
    ) -> RuntimeState:
        return build_runtime_state(
            config=self.config_getter(),
            is_running=is_running,
            status=status,
            started_at_utc=started_at_utc,
            last_error=last_error,
            status_message=status_message,
            metrics=self._metrics,
            subtitle_router_counters=self.subtitle_router.diagnostic_counters(),
            asr_diagnostics=self.asr_diagnostics(),
            translation_diagnostics=self.translation_diagnostics(),
            obs_caption_diagnostics=self.obs_caption_diagnostics(),
            resolved_asr=self._resolved_asr_provider(),
            current_asr_mode=self._current_asr_mode(),
            current_local_provider_preference=self._current_local_provider_preference(),
            is_browser_asr_mode=self._is_browser_asr_mode(),
        )

    def _set_state(
        self,
        *,
        is_running: bool,
        status: Literal["idle", "starting", "listening", "transcribing", "translating", "error"],
        started_at_utc: str | None,
        last_error: str | None = None,
        status_message: str | None = None,
    ) -> None:
        self._state = self._build_runtime_state(
            is_running=is_running,
            status=status,
            started_at_utc=started_at_utc,
            last_error=last_error,
            status_message=status_message,
        )

    def _record_metrics(self, **values: float | int | None) -> None:
        self._metrics = record_metrics(self._metrics, **values)

    def _runtime_material_status_snapshot(self, payload: dict[str, Any]) -> tuple[Any, ...]:
        return runtime_material_status_snapshot(payload)

    def _next_event_sequence(self, event_type: str) -> int:
        self._metrics, self._runtime_event_sequence = next_event_sequence(
            self._metrics,
            runtime_event_sequence=self._runtime_event_sequence,
            runtime_event_sequence_by_type=self._runtime_event_sequence_by_type,
            event_type=event_type,
        )
        return self._runtime_event_sequence

    def _enrich_event_payload(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._metrics, self._runtime_event_sequence, enriched = enrich_event_payload(
            self._metrics,
            payload=payload,
            event_type=event_type,
            runtime_event_sequence=self._runtime_event_sequence,
            runtime_event_sequence_by_type=self._runtime_event_sequence_by_type,
        )
        return enriched

    def _apply_translation_dispatcher_metrics(self, metrics: dict) -> None:
        if not isinstance(metrics, dict):
            return
        self._translation_dispatcher_snapshot = dict(metrics)
        self._metrics = apply_translation_dispatcher_metrics(self._metrics, snapshot=metrics)

    def _increment_metric(self, key: Literal["partial_updates_emitted", "finals_emitted", "suppressed_partial_updates"]) -> None:
        self._metrics = increment_metric(self._metrics, key)

    def _increment_counter_metric(
        self,
        key: Literal[
            "remote_audio_chunks_in",
            "remote_audio_bytes_in",
            "remote_audio_chunks_dropped",
            "vad_segments_partial",
            "vad_segments_final",
            "runtime_events_duplicate_suppressed",
            "runtime_status_broadcast_count",
            "runtime_status_duplicate_suppressed",
            "runtime_status_heartbeat_sent",
            "browser_worker_event_count",
            "browser_worker_event_coalesced",
            "overlay_stale_translation_suppressed",
            "overlay_payload_mismatch_count",
        ],
        amount: int = 1,
    ) -> None:
        self._metrics = increment_counter_metric(self._metrics, key, amount)

    @staticmethod
    def _pcm16_rms_level(audio: bytes) -> float:
        return pcm16_rms_level(audio)

    def _resolve_realtime_settings(self) -> dict[str, int | float | bool]:
        config = self.config_getter()
        asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
        if not isinstance(asr_config, dict):
            asr_config = {}

        status = self._asr_engine.status()
        if status.provider != "official_eu_parakeet_low_latency":
            return dict(self._LEGACY_VAD_SETTINGS)

        effective = dict(self._LEGACY_VAD_SETTINGS)
        realtime_settings = asr_config.get("realtime", {})
        if isinstance(realtime_settings, dict):
            for key in effective:
                value = realtime_settings.get(key)
                if isinstance(value, (int, float)):
                    effective[key] = int(value)
        for key in ("vad_mode", "energy_gate_enabled", "min_rms_for_recognition", "min_voiced_ratio", "first_partial_min_speech_ms"):
            value = realtime_settings.get(key) if isinstance(realtime_settings, dict) else None
            if key in {"energy_gate_enabled"}:
                effective[key] = bool(value) if value is not None else effective[key]
            elif key in {"min_rms_for_recognition", "min_voiced_ratio"}:
                if isinstance(value, (int, float)):
                    effective[key] = float(value)
            elif isinstance(value, (int, float)):
                effective[key] = int(value)
        return effective

    def _resolve_subtitle_lifecycle_settings(self) -> dict[str, int | bool]:
        config = self.config_getter()
        lifecycle = config.get("subtitle_lifecycle", {}) if isinstance(config, dict) else {}
        if not isinstance(lifecycle, dict):
            lifecycle = {}
        completed_ttl_ms = max(500, int(lifecycle.get("completed_block_ttl_ms", 4500) or 4500))
        source_ttl_ms = max(500, int(lifecycle.get("completed_source_ttl_ms", completed_ttl_ms) or completed_ttl_ms))
        translation_ttl_ms = max(500, int(lifecycle.get("completed_translation_ttl_ms", completed_ttl_ms) or completed_ttl_ms))
        return {
            "completed_block_ttl_ms": max(source_ttl_ms, translation_ttl_ms),
            "completed_source_ttl_ms": source_ttl_ms,
            "completed_translation_ttl_ms": translation_ttl_ms,
            "pause_to_finalize_ms": max(
                120,
                int(lifecycle.get("pause_to_finalize_ms", self._LEGACY_VAD_SETTINGS["finalization_hold_ms"]) or self._LEGACY_VAD_SETTINGS["finalization_hold_ms"]),
            ),
            "allow_early_replace_on_next_final": bool(lifecycle.get("allow_early_replace_on_next_final", True)),
            "sync_source_and_translation_expiry": bool(lifecycle.get("sync_source_and_translation_expiry", True)),
            "keep_completed_translation_during_active_partial": bool(
                lifecycle.get("keep_completed_translation_during_active_partial", True)
            ),
            "hard_max_phrase_ms": max(
                1000,
                int(lifecycle.get("hard_max_phrase_ms", self._LEGACY_VAD_SETTINGS["max_segment_ms"]) or self._LEGACY_VAD_SETTINGS["max_segment_ms"]),
            ),
        }

    def _apply_recognition_processing_settings(self) -> None:
        config = self.config_getter()
        asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
        if not isinstance(asr_config, dict):
            asr_config = {}
        try:
            rnnoise_strength = int(asr_config.get("rnnoise_strength", 70) or 70)
        except (TypeError, ValueError):
            rnnoise_strength = 70
        self._rnnoise_processor.configure(
            enabled=bool(asr_config.get("rnnoise_enabled", asr_config.get("experimental_noise_reduction_enabled", False))),
            strength=rnnoise_strength,
        )

    def _prepare_recognition_audio(self, audio: bytes) -> bytes:
        return prepare_recognition_audio(
            audio,
            rnnoise_enabled=bool(self.config_getter().get("asr", {}).get("rnnoise_enabled", False)),
            rnnoise_processor=self._rnnoise_processor,
        )

    def _apply_vad_tuning(self) -> None:
        settings = self._resolve_realtime_settings()
        lifecycle = self._resolve_subtitle_lifecycle_settings()
        self._vad.configure(
            mode=int(settings["vad_mode"]),
            silence_hold_ms=settings["silence_hold_ms"],
            finalization_hold_ms=int(lifecycle["pause_to_finalize_ms"]),
            min_speech_ms=settings["min_speech_ms"],
            partial_emit_interval_ms=settings["partial_emit_interval_ms"],
            max_segment_ms=int(lifecycle["hard_max_phrase_ms"]),
            energy_gate_enabled=bool(settings["energy_gate_enabled"]),
            min_rms_for_recognition=float(settings["min_rms_for_recognition"]),
            min_voiced_ratio=float(settings["min_voiced_ratio"]),
            first_partial_min_speech_ms=int(settings["first_partial_min_speech_ms"]),
        )
        self._effective_realtime_settings = settings
        self._effective_subtitle_lifecycle_settings = lifecycle

    def _should_emit_partial(self, segment_id: str, text: str) -> bool:
        normalized_text = " ".join(text.split())
        if not normalized_text:
            return False

        previous_text = self._last_partial_text_by_segment.get(segment_id, "")
        normalized_previous = " ".join(previous_text.split())
        if normalized_text == normalized_previous:
            return False

        coalescing_ms = int(self._effective_realtime_settings.get("partial_coalescing_ms", 0))
        min_delta_chars = int(self._effective_realtime_settings.get("partial_min_delta_chars", 0))
        previous_emit_at = self._last_partial_emit_monotonic_by_segment.get(segment_id, 0.0)
        elapsed_ms = (time.perf_counter() - previous_emit_at) * 1000.0 if previous_emit_at else None
        growth_chars = len(normalized_text) - len(normalized_previous)

        if (
            normalized_previous
            and coalescing_ms > 0
            and min_delta_chars > 0
            and growth_chars >= 0
            and growth_chars < min_delta_chars
            and elapsed_ms is not None
            and elapsed_ms < coalescing_ms
        ):
            return False

        return True

    def _should_drop_short_hallucination(self, *, text: str, duration_ms: int, is_final: bool) -> bool:
        normalized_text = " ".join(str(text or "").strip().split())
        if not normalized_text:
            return True

        lowered = normalized_text.casefold()
        word_count = len([part for part in lowered.replace("\n", " ").split(" ") if part.strip()])
        if lowered not in self._SHORT_HALLUCINATION_TOKENS:
            return False

        short_duration_limit_ms = 900 if is_final else 1100
        if duration_ms > short_duration_limit_ms:
            return False
        if word_count > 2:
            return False
        return True

    def _mark_partial_emitted(self, segment_id: str, text: str) -> None:
        self._last_partial_text_by_segment[segment_id] = " ".join(text.split())
        self._last_partial_emit_monotonic_by_segment[segment_id] = time.perf_counter()

    def _clear_partial_tracking(self, segment_id: str | None) -> None:
        if not segment_id:
            return
        self._last_partial_text_by_segment.pop(segment_id, None)
        self._last_partial_emit_monotonic_by_segment.pop(segment_id, None)

    async def _set_listening_if_current(
        self,
        *expected_statuses: Literal["listening", "transcribing", "translating"],
        last_error: str | None = None,
        status_message: str | None = None,
        broadcast: bool = True,
    ) -> None:
        if not self._state.is_running or self._state.status not in expected_statuses:
            return
        if broadcast:
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=self._state.started_at_utc,
                last_error=last_error,
                status_message=status_message,
            )
            return
        self._state = self._state.model_copy(
            update={
                "running": True,
                "is_running": True,
                "phase": "listening",
                "status": "listening",
                "last_error": last_error,
                "status_message": status_message,
            }
        )

    async def _set_runtime_state(
        self,
        *,
        is_running: bool,
        status: Literal["idle", "starting", "listening", "transcribing", "translating", "error"],
        started_at_utc: str | None,
        last_error: str | None = None,
        status_message: str | None = None,
    ) -> None:
        self._set_state(
            is_running=is_running,
            status=status,
            started_at_utc=started_at_utc,
            last_error=last_error,
            status_message=status_message,
        )
        await self._broadcast_runtime()

    def _build_startup_status_message(self) -> str:
        if self._is_browser_asr_mode():
            browser_lang = str(self._browser_asr_config().get("recognition_language", "ru-RU") or "ru-RU")
            if self._current_asr_mode() == EXPERIMENTAL_BROWSER_ASR_MODE:
                return (
                    f"Preparing experimental browser speech worker mode for {browser_lang}. "
                    "The popup window will open a live microphone track before recognition starts."
                )
            return f"Preparing browser speech worker mode for {browser_lang}. The popup window will capture audio."
        if self._uses_remote_event_source():
            return "Initializing controller relay mode and waiting for remote worker transcript events."
        if self._uses_remote_audio_source():
            return "Initializing worker ASR runtime and waiting for remote controller audio stream."
        asr_status = self._asr_engine.status()
        model_path = Path(asr_status.model_path) if asr_status.model_path else None
        if model_path is not None and not model_path.exists():
            return (
                "Preparing the first local Parakeet model download. "
                "In desktop mode there is no console, so watch the runtime log panel for status updates."
            )
        return "Initializing the ASR runtime and loading the Parakeet model."

    async def _capture_loop(self) -> None:
        try:
            while self._state.is_running:
                if self._uses_remote_audio_source():
                    remote_audio_queue = self._remote_audio_queue
                    if remote_audio_queue is None:
                        await asyncio.sleep(0.05)
                        continue
                    try:
                        chunk_data = await asyncio.wait_for(remote_audio_queue.get(), timeout=0.25)
                    except asyncio.TimeoutError:
                        if self._remote_audio_last_chunk_monotonic is not None:
                            self._record_metrics(
                                remote_audio_last_chunk_age_ms=(time.perf_counter() - self._remote_audio_last_chunk_monotonic) * 1000.0
                            )
                        continue
                    if not chunk_data:
                        continue
                    self._record_metrics(remote_audio_last_chunk_age_ms=0.0)
                else:
                    if self._audio_capture is None:
                        await asyncio.sleep(0.05)
                        continue
                    chunk = await asyncio.to_thread(self._audio_capture.read_chunk, 0.25)
                    if chunk is None:
                        continue
                    chunk_data = chunk.data
                vad_started = time.perf_counter()
                segments = self._vad.process_chunk(chunk_data)
                vad_elapsed_ms = (time.perf_counter() - vad_started) * 1000.0
                self._record_metrics(
                    vad_ms=vad_elapsed_ms,
                    vad_dropped_segments=int(getattr(self._vad, "_segment_dropped_count", 0) or 0),
                )
                if not segments:
                    continue
                partial_segments = sum(1 for segment in segments if segment.kind == "partial")
                final_segments = sum(1 for segment in segments if segment.kind == "final")
                if partial_segments > 0:
                    self._increment_counter_metric("vad_segments_partial", partial_segments)
                if final_segments > 0:
                    self._increment_counter_metric("vad_segments_final", final_segments)

                for segment in segments:
                    segment_id, revision, started_now = self._assign_segment_tracking(segment.kind)
                    if started_now:
                        await self._broadcast_transcript_segment_event(
                            TranscriptEvent(
                                event="partial" if segment.kind == "partial" else "final",
                                lifecycle_event="segment_started",
                                text="",
                                device_id=self._device_id,
                                sequence=self._sequence,
                                segment=TranscriptSegment(
                                    segment_id=segment_id,
                                    text="",
                                    is_partial=False,
                                    is_final=False,
                                    start_ms=0,
                                    end_ms=segment.duration_ms,
                                    source_lang=str(self.config_getter().get("source_lang", "auto")),
                                    provider=self._asr_engine.capabilities().provider_name,
                                    latency_ms=None,
                                    sequence=self._sequence,
                                    revision=revision,
                                ),
                            )
                        )
                    self._segment_queue.push(
                        AsrWorkItem(
                            kind=segment.kind,
                            audio=self._prepare_recognition_audio(segment.audio),
                            duration_ms=segment.duration_ms,
                            generation=self._asr_runtime_generation,
                            segment_id=segment_id,
                            revision=revision,
                            vad_ms=vad_elapsed_ms,
                        )
                    )
                    self._record_metrics(
                        asr_queue_depth=self._segment_queue.qsize(),
                        asr_partial_jobs_dropped=self._segment_queue.partial_jobs_dropped,
                    )
                    if segment.kind == "final":
                        self._active_segment_id = None
                        self._active_segment_revision = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._safe_stop_audio()
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=self._state.started_at_utc,
                last_error=str(exc),
            )

    async def _asr_loop(self) -> None:
        try:
            while self._state.is_running:
                work_item = await asyncio.to_thread(self._segment_queue.pop, 0.25)
                if work_item is None:
                    continue
                self._record_metrics(
                    asr_queue_depth=self._segment_queue.qsize(),
                    asr_partial_jobs_dropped=self._segment_queue.partial_jobs_dropped,
                )
                if work_item.generation != self._asr_runtime_generation:
                    self._record_metrics(
                        asr_stale_results_ignored=int(self._metrics.asr_stale_results_ignored or 0) + 1,
                    )
                    continue

                await self._set_runtime_state(
                    is_running=True,
                    status="transcribing",
                    started_at_utc=self._state.started_at_utc,
                )
                self._in_flight_transcribe_count += 1
                self._record_metrics(in_flight_transcribe_count=self._in_flight_transcribe_count)
                try:
                    result = await asyncio.to_thread(
                        self._asr_engine.run,
                        work_item.audio,
                        is_final=work_item.kind == "final",
                        segment_id=work_item.segment_id or None,
                    )
                finally:
                    self._in_flight_transcribe_count = max(0, self._in_flight_transcribe_count - 1)
                    self._record_metrics(in_flight_transcribe_count=self._in_flight_transcribe_count)
                if work_item.generation != self._asr_runtime_generation or not self._state.is_running:
                    self._record_metrics(
                        asr_stale_results_ignored=int(self._metrics.asr_stale_results_ignored or 0) + 1,
                    )
                    continue
                asr_elapsed_ms = (time.perf_counter() - work_item.created_at_monotonic) * 1000.0 - work_item.vad_ms
                total_elapsed_ms = (time.perf_counter() - work_item.created_at_monotonic) * 1000.0
                if work_item.kind == "final":
                    self._record_metrics(
                        vad_ms=work_item.vad_ms,
                        asr_final_ms=max(0.0, asr_elapsed_ms),
                        total_ms=total_elapsed_ms,
                    )
                else:
                    self._record_metrics(
                        vad_ms=work_item.vad_ms,
                        asr_partial_ms=max(0.0, asr_elapsed_ms),
                        total_ms=total_elapsed_ms,
                    )
                self._sequence += 1
                text = result.final if work_item.kind == "final" else result.partial
                if text:
                    if self._should_drop_short_hallucination(
                        text=text,
                        duration_ms=work_item.duration_ms,
                        is_final=work_item.kind == "final",
                    ):
                        if work_item.kind == "partial":
                            self._increment_metric("suppressed_partial_updates")
                        else:
                            self._clear_partial_tracking(work_item.segment_id)
                        await self._set_runtime_state(
                            is_running=True,
                            status="listening",
                            started_at_utc=self._state.started_at_utc,
                        )
                        continue
                    if work_item.kind == "partial":
                        segment_id = work_item.segment_id or ""
                        if not self._should_emit_partial(segment_id, text):
                            self._increment_metric("suppressed_partial_updates")
                            await self._set_runtime_state(
                                is_running=True,
                                status="listening",
                                started_at_utc=self._state.started_at_utc,
                            )
                            continue
                        self._mark_partial_emitted(segment_id, text)

                    lifecycle_event = "segment_finalized" if work_item.kind == "final" else "partial_updated"
                    segment = self._build_transcript_segment(
                        work_item=work_item,
                        text=text,
                        latency_ms=max(0.0, asr_elapsed_ms),
                    )
                    transcript_event = TranscriptEvent(
                        event=work_item.kind,
                        text=text,
                        device_id=self._device_id,
                        sequence=self._sequence,
                        lifecycle_event=lifecycle_event,
                        segment=segment,
                    )
                    await self._broadcast_transcript(transcript_event)
                    if work_item.kind == "final":
                        self._increment_metric("finals_emitted")
                        self._clear_partial_tracking(work_item.segment_id)
                        await self.subtitle_router.handle_transcript(transcript_event)
                        await self._obs_caption_output.publish_source_event(transcript_event)
                        await self._translation_dispatcher.submit_final(
                            sequence=self._sequence,
                            source_text=text,
                            source_lang=segment.source_lang,
                        )
                    else:
                        await self.subtitle_router.handle_transcript(transcript_event)
                        await self._obs_caption_output.publish_source_event(transcript_event)
                        self._increment_metric("partial_updates_emitted")
                elif work_item.kind == "final":
                    self._clear_partial_tracking(work_item.segment_id)
                await self._set_listening_if_current("transcribing", broadcast=False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._safe_stop_audio()
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=self._state.started_at_utc,
                last_error=str(exc),
            )

    async def _broadcast_external_segment_started(
        self,
        *,
        segment_id: str,
        revision: int,
        source_lang: str,
    ) -> None:
        await self._broadcast_transcript_segment_event(
            TranscriptEvent(
                event="partial",
                lifecycle_event="segment_started",
                text="",
                device_id=f"{self._browser_worker_provider_name()}_worker",
                sequence=self._sequence,
                segment=TranscriptSegment(
                    segment_id=segment_id,
                    text="",
                    is_partial=False,
                    is_final=False,
                    start_ms=0,
                    end_ms=0,
                    source_lang=source_lang,
                    provider=self._browser_worker_provider_name(),
                    latency_ms=None,
                    sequence=self._sequence,
                    revision=revision,
                ),
            )
        )

    def _build_external_transcript_segment(
        self,
        *,
        segment_id: str,
        revision: int,
        text: str,
        is_final: bool,
        source_lang: str,
        asr_result_created_at_ms: int | None = None,
        worker_send_started_at_ms: int | None = None,
        worker_message_sequence: int | None = None,
        worker_generation_id: int | None = None,
        worker_session_id: str | None = None,
        backend_received_at_ms: int | None = None,
        backend_published_to_router_at_ms: int | None = None,
    ) -> TranscriptSegment:
        return TranscriptSegment(
            segment_id=segment_id,
            text=text,
            is_partial=not is_final,
            is_final=is_final,
            start_ms=0,
            end_ms=0,
            source_lang=source_lang,
            provider=self._browser_worker_provider_name(),
            latency_ms=0.0,
            sequence=self._sequence,
            revision=revision,
            asr_result_created_at_ms=asr_result_created_at_ms,
            worker_send_started_at_ms=worker_send_started_at_ms,
            worker_message_sequence=worker_message_sequence,
            worker_generation_id=worker_generation_id,
            worker_session_id=worker_session_id,
            backend_received_at_ms=backend_received_at_ms,
            backend_published_to_router_at_ms=backend_published_to_router_at_ms,
        )

    async def browser_asr_worker_connected(self) -> None:
        self._external_worker_connected = True
        self._active_browser_worker_session_id = None
        self._active_browser_worker_generation_id = 0
        browser_mode = self._current_asr_mode() if self._is_browser_asr_mode() else None
        self._browser_asr_gateway.worker_connected(browser_mode=browser_mode)
        if self._state.is_running and self._is_browser_asr_mode():
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=self._state.started_at_utc,
                last_error=None,
                status_message=(
                    "Experimental browser speech worker connected. Press Start Recognition in the popup window."
                    if browser_mode == EXPERIMENTAL_BROWSER_ASR_MODE
                    else "Browser speech worker connected. Press Start Recognition in the popup window."
                ),
            )

    async def browser_asr_worker_disconnected(self) -> None:
        self._external_worker_connected = False
        self._active_browser_worker_session_id = None
        self._active_browser_worker_generation_id = 0
        browser_mode = self._current_asr_mode() if self._is_browser_asr_mode() else None
        self._browser_asr_gateway.worker_disconnected(browser_mode=browser_mode)
        segment_id = self._active_segment_id
        self._active_segment_id = None
        self._active_segment_revision = 0
        self._clear_partial_tracking(segment_id)
        await self.subtitle_router.clear_active_partial()
        if self._state.is_running and self._is_browser_asr_mode():
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=self._state.started_at_utc,
                status_message=(
                    "Experimental browser speech worker disconnected. Reopen or restart the browser recognition window."
                    if browser_mode == EXPERIMENTAL_BROWSER_ASR_MODE
                    else "Browser speech worker disconnected. Reopen or restart the browser recognition window."
                ),
            )

    async def update_browser_asr_worker_status(self, payload: dict[str, Any]) -> None:
        previous = self._browser_asr_gateway.diagnostics()
        self._browser_asr_gateway.update_status(payload)
        if self._state.is_running and self._is_browser_asr_mode():
            self._increment_counter_metric("browser_worker_event_count", 1)
            current = self._browser_asr_gateway.diagnostics()
            signature = (
                current.worker_connected,
                current.desired_running,
                current.pending_start,
                current.recognition_state,
                current.supervisor_state,
                current.degraded_reason,
                current.last_error,
                current.generation_id,
                current.session_id,
                current.client_segment_id,
                current.forced_final,
                current.no_speech_count,
                current.network_error_count,
                current.duplicate_partial_suppressed,
                current.duplicate_final_suppressed,
                current.late_forced_final_suppressed,
                current.mic_track_ready_state,
                current.mic_track_muted,
                current.mic_rms,
                current.mic_active_recent_ms,
            )
            if signature == self._last_browser_worker_status_signature and previous.model_dump() == current.model_dump():
                self._increment_counter_metric("browser_worker_event_coalesced", 1)
                return
            self._last_browser_worker_status_signature = signature
            await self._broadcast_runtime()

    async def ingest_external_asr_update(
        self,
        *,
        partial: str = "",
        final: str = "",
        is_final: bool = False,
        source_lang: str | None = None,
        generation_id: int | None = None,
        session_id: str | None = None,
        client_segment_id: str | None = None,
        forced_final: bool = False,
        asr_result_created_at_ms: int | None = None,
        worker_send_started_at_ms: int | None = None,
        worker_message_sequence: int | None = None,
        backend_received_at_ms: int | None = None,
    ) -> None:
        if not self._state.is_running or not self._is_browser_asr_mode():
            return
        normalized_session_id = str(session_id or "").strip() or None
        normalized_generation_id = max(0, int(generation_id or 0))
        if normalized_session_id:
            if self._active_browser_worker_session_id and normalized_session_id != self._active_browser_worker_session_id:
                self._increment_counter_metric("browser_worker_event_coalesced", 1)
                self._browser_asr_gateway.update_status(
                    {"stale_worker_events_ignored": self._browser_asr_gateway.diagnostics().stale_worker_events_ignored + 1}
                )
                return
            self._active_browser_worker_session_id = normalized_session_id
        if normalized_generation_id:
            if normalized_generation_id < self._active_browser_worker_generation_id:
                self._increment_counter_metric("browser_worker_event_coalesced", 1)
                self._browser_asr_gateway.update_status(
                    {"stale_worker_events_ignored": self._browser_asr_gateway.diagnostics().stale_worker_events_ignored + 1}
                )
                return
            self._active_browser_worker_generation_id = normalized_generation_id
        self._increment_counter_metric("browser_worker_event_count", 1)

        normalized_source_lang = str(source_lang or self._browser_asr_source_lang() or "auto").strip().lower() or "auto"
        partial_text = str(partial or "").strip()
        final_text = str(final or "").strip()
        normalized_client_segment_id = str(client_segment_id or "").strip() or None
        backend_published_to_router_at_ms = int(time.time() * 1000)
        if is_final and not final_text and partial_text:
            final_text = partial_text

        if partial_text and not is_final:
            segment_id, revision, started_now = self._assign_segment_tracking(
                "partial",
                preferred_segment_id=normalized_client_segment_id,
            )
            if started_now:
                await self._broadcast_external_segment_started(
                    segment_id=segment_id,
                    revision=revision,
                    source_lang=normalized_source_lang,
                )
            if not self._should_emit_partial(segment_id, partial_text):
                self._increment_metric("suppressed_partial_updates")
                return
            self._mark_partial_emitted(segment_id, partial_text)
            self._sequence += 1
            transcript_event = TranscriptEvent(
                event="partial",
                text=partial_text,
                device_id=f"{self._browser_worker_provider_name()}_worker",
                sequence=self._sequence,
                lifecycle_event="partial_updated",
                segment=self._build_external_transcript_segment(
                    segment_id=segment_id,
                    revision=revision,
                    text=partial_text,
                    is_final=False,
                    source_lang=normalized_source_lang,
                    asr_result_created_at_ms=asr_result_created_at_ms,
                    worker_send_started_at_ms=worker_send_started_at_ms,
                    worker_message_sequence=worker_message_sequence,
                    worker_generation_id=normalized_generation_id or None,
                    worker_session_id=normalized_session_id,
                    backend_received_at_ms=backend_received_at_ms,
                    backend_published_to_router_at_ms=backend_published_to_router_at_ms,
                ),
            )
            self._browser_asr_gateway.note_partial(
                text_len=len(partial_text),
                source_lang=normalized_source_lang,
                sequence=transcript_event.sequence,
            )
            await self._broadcast_transcript(transcript_event)
            await self.subtitle_router.handle_transcript(transcript_event)
            await self._obs_caption_output.publish_source_event(transcript_event)
            self._increment_metric("partial_updates_emitted")
            await self._set_listening_if_current(
                "listening",
                last_error=None,
                status_message="Browser speech recognition is active.",
                broadcast=False,
            )

        if is_final and final_text:
            segment_id, revision, started_now = self._assign_segment_tracking(
                "final",
                preferred_segment_id=normalized_client_segment_id,
            )
            if started_now:
                await self._broadcast_external_segment_started(
                    segment_id=segment_id,
                    revision=revision,
                    source_lang=normalized_source_lang,
                )
            self._clear_partial_tracking(segment_id)
            self._sequence += 1
            transcript_event = TranscriptEvent(
                event="final",
                text=final_text,
                device_id=f"{self._browser_worker_provider_name()}_worker",
                sequence=self._sequence,
                lifecycle_event="segment_finalized",
                segment=self._build_external_transcript_segment(
                    segment_id=segment_id,
                    revision=revision,
                    text=final_text,
                    is_final=True,
                    source_lang=normalized_source_lang,
                    asr_result_created_at_ms=asr_result_created_at_ms,
                    worker_send_started_at_ms=worker_send_started_at_ms,
                    worker_message_sequence=worker_message_sequence,
                    worker_generation_id=normalized_generation_id or None,
                    worker_session_id=normalized_session_id,
                    backend_received_at_ms=backend_received_at_ms,
                    backend_published_to_router_at_ms=backend_published_to_router_at_ms,
                ),
            )
            self._browser_asr_gateway.note_final(
                text_len=len(final_text),
                source_lang=normalized_source_lang,
                sequence=transcript_event.sequence,
            )
            await self._broadcast_transcript(transcript_event)
            self._increment_metric("finals_emitted")
            await self.subtitle_router.handle_transcript(transcript_event)
            await self._obs_caption_output.publish_source_event(transcript_event)
            await self._translation_dispatcher.submit_final(
                sequence=self._sequence,
                source_text=final_text,
                source_lang=normalized_source_lang,
            )
            self._active_segment_id = None
            self._active_segment_revision = 0
            await self._set_listening_if_current(
                "listening",
                last_error=None,
                status_message="Browser speech recognition is active.",
                broadcast=False,
            )

    async def start(self, *, has_audio_inputs: bool, device_id: str | None) -> RuntimeState:
        if self._state.is_running:
            return self._state

        self._runtime_loop = asyncio.get_running_loop()
        self._latest_runtime_status_message = None
        self._metrics = RuntimeMetrics()
        self._in_flight_transcribe_count = 0
        self._translation_dispatcher_snapshot = {}
        self._translation_dispatcher = TranslationDispatcher(
            self._translation_engine,
            self.config_getter,
            self._publish_translation_dispatch_event,
            self.subtitle_router.is_sequence_relevant_for_translation,
            self._apply_translation_dispatcher_metrics,
            structured_logger=self._structured_runtime_logger,
        )
        self._remote_audio_queue = asyncio.Queue(maxsize=256)
        asr_mode = self._current_asr_mode()
        if self._current_remote_role() == REMOTE_ROLE_WORKER and self._is_browser_asr_mode(asr_mode):
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=None,
                last_error="Remote worker mode supports AI runtime only. Browser speech mode is not allowed.",
                status_message=None,
            )
            return self._state
        use_remote_audio_source = self._uses_remote_audio_source()
        use_remote_event_source = self._uses_remote_event_source()
        if not self._is_browser_asr_mode(asr_mode) and not use_remote_audio_source and not use_remote_event_source and not has_audio_inputs:
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=None,
                last_error="No input audio devices found.",
            )
            return self._state

        await self._set_runtime_state(
            is_running=False,
            status="starting",
            started_at_utc=None,
            status_message=self._build_startup_status_message(),
        )

        try:
            if not self._is_browser_asr_mode(asr_mode) and not use_remote_event_source:
                asr_status = await asyncio.to_thread(self._asr_engine.initialize_runtime)
                self._apply_vad_tuning()
                if not asr_status.ready:
                    await self._set_runtime_state(
                        is_running=False,
                        status="error",
                        started_at_utc=None,
                        last_error=asr_status.message,
                        status_message=None,
                    )
                    return self._state
            self._device_id = "remote_webrtc_controller" if use_remote_audio_source else device_id
            if not self._is_browser_asr_mode(asr_mode):
                self._external_worker_connected = False
            if not self._is_browser_asr_mode(asr_mode) and not use_remote_audio_source:
                self._audio_capture = AudioCapture()
                self._audio_capture.start(device_id=device_id)
            if use_remote_audio_source:
                await self._clear_remote_audio_queue()
                self._remote_audio_connected = False
                self._remote_audio_session_id = None
                self._remote_audio_last_chunk_monotonic = None
            await self._obs_caption_output.start()
            await self._obs_caption_output.apply_live_settings(self.config_getter())
            self._reset_export_session()
            await self.subtitle_router.reset()
            self._vad.reset()
            self._asr_engine.reset_runtime_state()
            self._segment_queue.clear()
            self._sequence = 0
            self._asr_runtime_generation += 1
            self._runtime_event_sequence = 0
            self._runtime_event_sequence_by_type.clear()
            self._last_runtime_status_signature = None
            self._last_runtime_status_broadcast_monotonic = 0.0
            self._last_browser_worker_status_signature = None
            self._last_partial_text_by_segment.clear()
            self._last_partial_emit_monotonic_by_segment.clear()
            started_at = datetime.now(timezone.utc).isoformat()
            self._session_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            self._session_started_at_utc = started_at
            self._session_started_at_monotonic = time.perf_counter()
            self._active_runtime_mode = asr_mode
            self._active_local_provider_preference = (
                self._current_local_provider_preference() if asr_mode == LOCAL_ASR_MODE else None
            )
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=started_at,
                status_message=(
                    "Controller relay mode is ready and waiting for remote worker events."
                    if use_remote_event_source
                    else
                    "Worker runtime is ready and waiting for remote WebRTC audio."
                    if use_remote_audio_source
                    else
                    (
                        (
                            "Experimental browser speech worker connected. Press Start Recognition in the popup window."
                            if asr_mode == EXPERIMENTAL_BROWSER_ASR_MODE
                            else "Browser speech worker connected. Press Start Recognition in the popup window."
                        )
                        if self._external_worker_connected
                        else (
                            "Waiting for the experimental browser speech worker window to connect."
                            if asr_mode == EXPERIMENTAL_BROWSER_ASR_MODE
                            else "Waiting for the browser speech worker window to connect."
                        )
                    )
                    if self._is_browser_asr_mode(asr_mode)
                    else None
                ),
            )
            if not self._is_browser_asr_mode(asr_mode) and not use_remote_event_source:
                self._capture_task = asyncio.create_task(self._capture_loop())
                self._asr_task = asyncio.create_task(self._asr_loop())
        except Exception as exc:
            await self._safe_stop_audio()
            await self._obs_caption_output.stop()
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=None,
                last_error=str(exc),
                status_message=None,
            )
        return self._state

    async def _safe_stop_audio(self) -> None:
        if self._audio_capture is not None:
            await asyncio.to_thread(self._audio_capture.stop)
            self._audio_capture = None

    async def stop(self) -> RuntimeState:
        self._latest_runtime_status_message = None
        self._asr_runtime_generation += 1
        self._set_state(is_running=False, status="idle", started_at_utc=None, last_error=None)
        self._segment_queue.clear()
        tasks = [task for task in (self._capture_task, self._asr_task) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._capture_task = None
        self._asr_task = None
        self._external_worker_connected = False
        self._active_browser_worker_session_id = None
        self._active_browser_worker_generation_id = 0
        self._active_runtime_mode = None
        self._active_local_provider_preference = None
        self._remote_audio_connected = False
        self._remote_audio_session_id = None
        self._remote_audio_last_chunk_monotonic = None
        await self._safe_stop_audio()
        await self._obs_caption_output.stop()
        stopped_at_utc = datetime.now(timezone.utc).isoformat()
        export_error: str | None = None
        try:
            self._export_session_files(stopped_at_utc=stopped_at_utc)
        except Exception as exc:
            export_error = str(exc)
        await self.subtitle_router.reset()
        await self._translation_dispatcher.stop()
        self._segment_queue.clear()
        self._vad.reset()
        await asyncio.to_thread(self._asr_engine.unload_runtime_state)
        self._last_partial_text_by_segment.clear()
        self._last_partial_emit_monotonic_by_segment.clear()
        await self._clear_remote_audio_queue()
        self._remote_audio_queue = None
        self._reset_export_session()
        self._metrics = RuntimeMetrics()
        self._in_flight_transcribe_count = 0
        self._last_runtime_status_signature = None
        self._last_runtime_status_broadcast_monotonic = 0.0
        self._last_browser_worker_status_signature = None
        self._runtime_loop = None
        if export_error:
            self._state = self._state.model_copy(update={"last_error": f"Export error: {export_error}"})
        await self._broadcast_runtime()
        return self._state

    async def _clear_remote_audio_queue(self) -> None:
        await clear_async_queue(self._remote_audio_queue)

    async def remote_audio_ingest_connected(self, *, session_id: str | None = None) -> None:
        self._remote_audio_connected = True
        self._remote_audio_session_id = str(session_id or "").strip() or None
        self._remote_audio_last_chunk_monotonic = time.perf_counter()
        await self._set_listening_if_current(
            "listening",
            last_error=None,
            status_message="Remote controller audio stream is connected.",
        )

    async def remote_audio_ingest_disconnected(self) -> None:
        self._remote_audio_connected = False
        self._remote_audio_last_chunk_monotonic = None
        await self._set_listening_if_current(
            "listening",
            last_error=None,
            status_message="Waiting for remote controller audio stream.",
        )

    async def ingest_remote_audio_chunk(self, payload: bytes) -> bool:
        if not self._state.is_running:
            return False
        if not self._uses_remote_audio_source():
            return False
        audio = bytes(payload or b"")
        if not audio:
            return False
        if len(audio) % 2 != 0:
            audio = audio[:-1]
            if not audio:
                return False
        remote_audio_queue = self._remote_audio_queue
        if remote_audio_queue is None:
            return False
        if remote_audio_queue.full():
            try:
                remote_audio_queue.get_nowait()
                self._increment_counter_metric("remote_audio_chunks_dropped", 1)
            except asyncio.QueueEmpty:
                pass
        await remote_audio_queue.put(audio)
        self._increment_counter_metric("remote_audio_chunks_in", 1)
        self._increment_counter_metric("remote_audio_bytes_in", len(audio))
        self._record_metrics(
            remote_audio_level_rms=self._pcm16_rms_level(audio),
            remote_audio_last_chunk_age_ms=0.0,
        )
        self._remote_audio_last_chunk_monotonic = time.perf_counter()
        return True

    async def ingest_remote_transcript_event(self, payload: dict) -> bool:
        if not self._state.is_running or not self._uses_remote_event_source():
            return False
        if not isinstance(payload, dict):
            return False
        try:
            event = TranscriptEvent.model_validate(payload)
        except Exception:
            return False
        if event.event == "partial":
            await self._set_runtime_state(
                is_running=True,
                status="transcribing",
                started_at_utc=self._state.started_at_utc,
                status_message="Receiving remote worker transcript stream.",
            )
        await self._broadcast_transcript(event)
        await self.subtitle_router.handle_transcript(event)
        await self._obs_caption_output.publish_source_event(event)
        if event.event == "final":
            self._increment_metric("finals_emitted")
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=self._state.started_at_utc,
                status_message="Remote worker transcript stream is active.",
            )
        return True

    async def ingest_remote_translation_event(self, payload: dict) -> bool:
        if not self._state.is_running or not self._uses_remote_event_source():
            return False
        if not isinstance(payload, dict):
            return False
        try:
            event = TranslationEvent.model_validate(payload)
        except Exception:
            return False
        await self._set_runtime_state(
            is_running=True,
            status="translating",
            started_at_utc=self._state.started_at_utc,
            status_message="Receiving remote worker translation stream.",
        )
        await self._broadcast_translation(event)
        await self.subtitle_router.handle_translation(event)
        await self._set_runtime_state(
            is_running=True,
            status="listening",
            started_at_utc=self._state.started_at_utc,
            status_message="Remote worker transcript stream is active.",
        )
        return True

    def status(self) -> RuntimeState:
        self._apply_vad_tuning()
        if self._uses_remote_audio_source():
            if self._remote_audio_last_chunk_monotonic is not None:
                self._record_metrics(
                    remote_audio_last_chunk_age_ms=(time.perf_counter() - self._remote_audio_last_chunk_monotonic) * 1000.0
                )
        else:
            self._record_metrics(remote_audio_last_chunk_age_ms=None)
        self._state = self._build_runtime_state(
            is_running=self._state.is_running,
            status=self._state.status,
            started_at_utc=self._state.started_at_utc,
            last_error=self._state.last_error,
            status_message=self._state.status_message,
        )
        return self._state

    def asr_status(self):
        if self._is_browser_asr_mode():
            browser_mode = self._current_asr_mode()
            message = (
                "Experimental browser speech worker is connected."
                if self._external_worker_connected
                else "Experimental browser speech mode is configured. Open the browser worker window to capture audio."
            ) if browser_mode == EXPERIMENTAL_BROWSER_ASR_MODE else (
                "Browser speech worker is connected."
                if self._external_worker_connected
                else "Browser speech mode is configured. Open the browser worker window to capture audio."
            )
            return AsrProviderStatus(
                provider=browser_mode,
                ready=True,
                message=message,
                requested_provider=browser_mode,
                requested_device_policy="browser_window",
                supports_gpu=False,
                supports_partials=True,
                supports_streaming=True,
                partials_supported=True,
                selected_device="browser",
                selected_execution_provider="webkitSpeechRecognition",
                runtime_initialized=self._state.is_running,
            )
        return self._asr_engine.status()

    def translation_diagnostics(self) -> TranslationDiagnostics:
        return summarize_translation_diagnostics(
            config_getter=self.config_getter,
            translation_engine=self._translation_engine,
            translation_dispatcher_snapshot=self._translation_dispatcher_snapshot,
        )

    def obs_caption_diagnostics(self) -> ObsCaptionDiagnostics:
        return self._obs_caption_output.diagnostics()

    def asr_diagnostics(self) -> AsrDiagnostics:
        try:
            resolved_asr = self._resolved_asr_provider()
            if self._is_browser_asr_mode():
                browser_mode = self._current_asr_mode()
                browser_config = self._browser_asr_config()
                browser_lang = str(browser_config.get("recognition_language", "ru-RU") or "ru-RU")
                browser_worker = self._browser_asr_gateway.diagnostics()
                worker_message = (
                    "Experimental browser speech worker is connected."
                    if self._external_worker_connected
                    else "Open the experimental browser speech window and start recognition there."
                ) if browser_mode == EXPERIMENTAL_BROWSER_ASR_MODE else (
                    "Browser speech worker is connected."
                    if self._external_worker_connected
                    else "Open the browser speech window and start recognition there."
                )
                return AsrDiagnostics(
                    mode=str(resolved_asr.get("mode", browser_mode) or browser_mode),
                    provider_preference=str(
                        resolved_asr.get("provider_preference", self._current_local_provider_preference())
                        or self._current_local_provider_preference()
                    ),
                    effective_provider=str(resolved_asr.get("effective_provider", browser_mode) or browser_mode),
                    provider=browser_mode,
                    provider_label="Browser Google Speech Experimental"
                    if browser_mode == EXPERIMENTAL_BROWSER_ASR_MODE
                    else "Browser Google Speech",
                    provider_kind=str(resolved_asr.get("provider_kind", "") or "") or "browser_worker",
                    provider_mode_kind="browser_speech",
                    uses_browser_worker=True,
                    uses_backend_audio_capture=False,
                    true_streaming=True,
                    requested_provider=browser_mode,
                    requested_device_policy="browser_window",
                    requested_device="browser_window",
                    cuda_available=False,
                    supports_gpu=False,
                    supports_partials=True,
                    supports_streaming=True,
                    supports_word_timestamps=False,
                    supports_timestamps=False,
                    gpu_requested=False,
                    gpu_available=False,
                    torch_built_with_cuda=False,
                    torch_cuda_is_available=False,
                    torch_device_count=0,
                    degraded_mode=bool(browser_worker.degraded_reason),
                    selected_device="browser",
                    selected_execution_provider="webkitSpeechRecognition",
                    partials_supported=True,
                    sample_rate=None,
                    recognition_noise_reduction_enabled=False,
                    rnnoise_strength=0,
                    rnnoise_available=False,
                    rnnoise_active=False,
                    rnnoise_message="RNNoise is not used in browser speech mode.",
                    provider_phase=str(browser_worker.recognition_state or browser_worker.supervisor_state or "idle"),
                    provider_message=worker_message,
                    provider_error_kind=str(browser_worker.error_type or "") or None,
                    provider_last_error=str(browser_worker.last_error or "") or None,
                    message=(
                        f"{worker_message} Recognition language: {browser_lang}. "
                        "The worker may fall back to default start() if audio-track start is rejected."
                        if browser_mode == EXPERIMENTAL_BROWSER_ASR_MODE
                        else f"{worker_message} Recognition language: {browser_lang}."
                    ),
                    runtime_initialized=self._state.is_running,
                    browser_worker=browser_worker,
                )
            diagnostics = self._asr_engine.diagnostics()
            rnnoise_status = self._rnnoise_processor.status()
            config = self.config_getter()
            asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
            model_load_mode = str(asr_config.get("model_load_mode", "auto") or "auto") if isinstance(asr_config, dict) else "auto"
            model_revision = str(asr_config.get("model_revision", "") or "") if isinstance(asr_config, dict) else ""
            inference_mode_enabled = bool(getattr(self._asr_engine.provider, "inference_mode_enabled", False))
            return AsrDiagnostics(
                mode=str(resolved_asr.get("mode", LOCAL_ASR_MODE) or LOCAL_ASR_MODE),
                provider_preference=str(
                    resolved_asr.get("provider_preference", diagnostics.requested_provider or DEFAULT_PARAKEET_PROVIDER)
                    or diagnostics.requested_provider
                    or DEFAULT_PARAKEET_PROVIDER
                ),
                effective_provider=str(resolved_asr.get("effective_provider", diagnostics.provider_name) or diagnostics.provider_name),
                provider=diagnostics.provider_name,
                provider_label=(
                    "Official EU Parakeet Low Latency"
                    if diagnostics.provider_name == "official_eu_parakeet_low_latency"
                    else "Official EU Parakeet"
                ),
                provider_kind=str(resolved_asr.get("provider_kind", "") or "") or "local_parakeet",
                provider_mode_kind="local_ai",
                uses_browser_worker=False,
                uses_backend_audio_capture=True,
                true_streaming=diagnostics.provider_name == "official_eu_parakeet_low_latency",
                requested_provider=diagnostics.requested_provider,
                requested_device_policy=diagnostics.requested_device_policy,
                requested_device="cuda" if diagnostics.gpu_requested else "cpu",
                model_load_mode=model_load_mode,
                model_repo=OFFICIAL_EU_PARAKEET_REPO,
                model_revision=model_revision,
                model_path=diagnostics.model_path,
                model_integrity_state="present" if diagnostics.model_path else "pending_download",
                supports_gpu=diagnostics.supports_gpu,
                supports_partials=diagnostics.supports_partials,
                supports_streaming=diagnostics.supports_streaming,
                supports_word_timestamps=diagnostics.supports_word_timestamps,
                supports_timestamps=diagnostics.supports_word_timestamps,
                gpu_requested=diagnostics.gpu_requested,
                gpu_available=diagnostics.gpu_available,
                cuda_available=diagnostics.torch_cuda_is_available,
                torch_version=diagnostics.torch_version,
                torch_built_with_cuda=diagnostics.torch_built_with_cuda,
                torch_cuda_is_available=diagnostics.torch_cuda_is_available,
                torch_cuda_version=diagnostics.torch_cuda_version,
                torch_device_count=diagnostics.torch_device_count,
                first_gpu_name=diagnostics.first_gpu_name,
                python_executable=diagnostics.python_executable,
                venv_path=diagnostics.venv_path,
                degraded_mode=diagnostics.degraded_mode,
                fallback_reason=diagnostics.fallback_reason,
                cpu_fallback_reason=diagnostics.cpu_fallback_reason,
                selected_device=diagnostics.actual_selected_device,
                selected_execution_provider=diagnostics.actual_execution_provider,
                partials_supported=diagnostics.supports_partials,
                sample_rate=getattr(self._audio_capture, "sample_rate", None) or self._asr_engine.sample_rate,
                audio_frame_duration_ms=getattr(self._vad, "frame_duration_ms", None),
                vad_mode=getattr(self._vad, "vad_mode", None),
                vad_partial_interval_ms=getattr(self._vad, "partial_interval_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_min_speech_ms=getattr(self._vad, "min_speech_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_first_partial_min_speech_ms=getattr(self._vad, "first_partial_min_speech_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_silence_padding_ms=getattr(self._vad, "silence_hold_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_finalization_hold_ms=getattr(self._vad, "finalization_hold_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_max_segment_ms=getattr(self._vad, "max_segment_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_energy_gate_enabled=bool(getattr(self._vad, "energy_gate_enabled", False)),
                vad_min_rms_for_recognition=float(getattr(self._vad, "min_rms_for_recognition", 0.0)),
                vad_min_voiced_ratio=float(getattr(self._vad, "min_voiced_ratio", 0.0)),
                realtime_chunk_window_ms=int(self._effective_realtime_settings.get("chunk_window_ms", 0) or 0),
                realtime_chunk_overlap_ms=int(self._effective_realtime_settings.get("chunk_overlap_ms", 0) or 0),
                partial_min_delta_chars=int(self._effective_realtime_settings.get("partial_min_delta_chars", 0) or 0),
                partial_coalescing_ms=int(self._effective_realtime_settings.get("partial_coalescing_ms", 0) or 0),
                recognition_noise_reduction_enabled=rnnoise_status.enabled,
                rnnoise_strength=rnnoise_status.strength,
                rnnoise_available=rnnoise_status.backend_available,
                rnnoise_active=rnnoise_status.active,
                rnnoise_backend=rnnoise_status.backend_name,
                rnnoise_uses_resample=rnnoise_status.uses_resample,
                rnnoise_input_sample_rate=rnnoise_status.input_sample_rate,
                rnnoise_processing_sample_rate=rnnoise_status.processing_sample_rate,
                rnnoise_frame_size_samples=rnnoise_status.frame_size_samples,
                rnnoise_message=rnnoise_status.message,
                message=diagnostics.message,
                runtime_initialized=diagnostics.runtime_initialized,
                provider_phase="listening" if self._state.is_running else "idle",
                provider_message=diagnostics.message,
                provider_error_kind="cpu_fallback" if diagnostics.cpu_fallback_reason else None,
                provider_last_error=diagnostics.fallback_reason or diagnostics.cpu_fallback_reason,
                parakeet_generation=self._asr_runtime_generation,
                asr_queue_depth=self._segment_queue.qsize(),
                asr_partial_jobs_dropped=self._segment_queue.partial_jobs_dropped,
                asr_stale_results_ignored=int(self._metrics.asr_stale_results_ignored or 0),
                in_flight_transcribe_count=self._in_flight_transcribe_count,
                inference_mode_enabled=inference_mode_enabled,
            )
        except Exception as exc:
            return AsrDiagnostics(
                mode=LOCAL_ASR_MODE,
                provider_preference=DEFAULT_PARAKEET_PROVIDER,
                effective_provider="unknown",
                provider="unknown",
                provider_label="Unknown ASR",
                provider_kind="unknown",
                provider_mode_kind="unknown",
                uses_browser_worker=False,
                uses_backend_audio_capture=False,
                true_streaming=False,
                requested_provider="unknown",
                requested_device_policy="unknown",
                requested_device="unknown",
                model_load_mode="auto",
                model_repo=OFFICIAL_EU_PARAKEET_REPO,
                model_revision="",
                model_integrity_state="unknown",
                supports_gpu=False,
                supports_partials=False,
                supports_streaming=False,
                supports_word_timestamps=False,
                supports_timestamps=False,
                cuda_available=False,
                torch_built_with_cuda=False,
                torch_cuda_is_available=False,
                torch_device_count=0,
                degraded_mode=True,
                fallback_reason=f"ASR diagnostics unavailable: {exc}",
                selected_device="unknown",
                selected_execution_provider="unknown",
                partials_supported=False,
                sample_rate=self._asr_engine.sample_rate,
                audio_frame_duration_ms=getattr(self._vad, "frame_duration_ms", None),
                vad_mode=getattr(self._vad, "vad_mode", None),
                vad_partial_interval_ms=getattr(self._vad, "partial_interval_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_min_speech_ms=getattr(self._vad, "min_speech_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_first_partial_min_speech_ms=getattr(self._vad, "first_partial_min_speech_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_silence_padding_ms=getattr(self._vad, "silence_hold_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_finalization_hold_ms=getattr(self._vad, "finalization_hold_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_max_segment_ms=getattr(self._vad, "max_segment_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_energy_gate_enabled=bool(getattr(self._vad, "energy_gate_enabled", False)),
                vad_min_rms_for_recognition=float(getattr(self._vad, "min_rms_for_recognition", 0.0)),
                vad_min_voiced_ratio=float(getattr(self._vad, "min_voiced_ratio", 0.0)),
                realtime_chunk_window_ms=int(self._effective_realtime_settings.get("chunk_window_ms", 0) or 0),
                realtime_chunk_overlap_ms=int(self._effective_realtime_settings.get("chunk_overlap_ms", 0) or 0),
                message=f"ASR diagnostics unavailable: {exc}",
                provider_phase="error",
                provider_message="ASR diagnostics unavailable.",
                provider_error_kind=type(exc).__name__,
                provider_last_error=str(exc),
            )

    def _assign_segment_tracking(self, kind: str, *, preferred_segment_id: str | None = None) -> tuple[str, int, bool]:
        started_now = False
        _ = kind
        normalized_preferred_segment_id = str(preferred_segment_id or "").strip() or None
        if normalized_preferred_segment_id and normalized_preferred_segment_id != self._active_segment_id:
            self._clear_partial_tracking(self._active_segment_id)
            self._active_segment_id = normalized_preferred_segment_id
            self._active_segment_revision = 0
            started_now = True
        elif self._active_segment_id is None:
            self._segment_counter += 1
            self._active_segment_id = f"segment-{self._segment_counter}"
            self._active_segment_revision = 0
            started_now = True
        self._active_segment_revision += 1
        return self._active_segment_id, self._active_segment_revision, started_now

    def _build_transcript_segment(self, *, work_item: AsrWorkItem, text: str, latency_ms: float) -> TranscriptSegment:
        capabilities = self._asr_engine.capabilities()
        return TranscriptSegment(
            segment_id=work_item.segment_id or f"segment-{self._sequence}",
            text=text,
            is_partial=work_item.kind == "partial",
            is_final=work_item.kind == "final",
            start_ms=0,
            end_ms=work_item.duration_ms,
            source_lang=str(self.config_getter().get("source_lang", "auto")),
            provider=capabilities.provider_name,
            latency_ms=round(float(latency_ms), 2),
            sequence=self._sequence,
            revision=work_item.revision,
        )
