"""State, broadcast, and runtime metrics helpers for RuntimeOrchestrator."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Literal

from backend.core.runtime.asr_runtime_controller import is_browser_asr_mode
from backend.core.runtime.audio_runtime_controller import pcm16_rms_level
from backend.core.runtime.output_fanout_controller import OutputFanoutController
from backend.core.runtime.runtime_metrics_collector import runtime_material_status_snapshot
from backend.core.runtime.runtime_state_controller import RuntimeStateController
from backend.core.runtime.runtime_status_builder import build_overlay_runtime_status, build_runtime_state
from backend.models import OverlayRuntimeStatus, RuntimeState, TranscriptEvent, TranslationEvent
from backend.schemas.overlay_schema import SubtitlePayloadEvent


class RuntimeOrchestratorStateMetricsMixin:
    def _emit_asr_runtime_status(self, message: str) -> None:
        normalized = str(message or "").strip()
        if not normalized:
            return
        if normalized == self._latest_runtime_status_message:
            return
        self._latest_runtime_status_message = normalized
        loop = self._runtime_loop
        if loop is None or loop.is_closed():
            # _runtime_loop is assigned in pre_start(); if this callback fires before that
            # (e.g. a very early ASR init callback), try to reach the running loop directly.
            try:
                loop = asyncio.get_event_loop()
                if loop is None or loop.is_closed() or not loop.is_running():
                    return
            except RuntimeError:
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

    def set_browser_asr_transport_probe(self, probe: Callable[[], bool] | None) -> None:
        """Optional callback from app bootstrap: BrowserAsrService.has_active_transport."""
        self._browser_transport_probe = probe

    def _browser_policy_can_send(self) -> bool:
        if self._browser_transport_probe is None:
            return False
        try:
            return bool(self._browser_transport_probe())
        except Exception:
            return False

    def _current_asr_mode(self) -> str:
        return self._asr_mode.current_mode(state_is_running=self._state.is_running)

    def _is_browser_asr_mode(self, mode: str | None = None) -> bool:
        return is_browser_asr_mode(mode or self._current_asr_mode())

    def _resolved_asr_provider(self) -> dict[str, Any]:
        return self._asr_mode.resolve(state_is_running=self._state.is_running)

    def _current_local_provider_preference(self) -> str:
        return self._asr_mode.current_local_provider_preference(state_is_running=self._state.is_running)

    def _browser_asr_config(self) -> dict[str, object]:
        return self._asr_mode.browser_config()

    def _browser_asr_source_lang(self) -> str:
        return self._asr_mode.browser_source_lang()

    def _browser_worker_provider_name(self) -> str:
        return self._asr_mode.browser_worker_provider_name(state_is_running=self._state.is_running)

    def _current_remote_role(self) -> str:
        return self._asr_mode.current_remote_role()

    def _uses_remote_audio_source(self) -> bool:
        return self._asr_mode.uses_remote_audio_source(state_is_running=self._state.is_running)

    def _is_remote_enabled(self) -> bool:
        return self._asr_mode.is_remote_enabled()

    def _uses_remote_event_source(self) -> bool:
        return self._asr_mode.uses_remote_event_source(state_is_running=self._state.is_running)

    async def _broadcast_runtime(self) -> None:
        if not hasattr(self, "_state_controller") or self._state_controller is None:  # type: ignore[attr-defined]
            heartbeat = int(getattr(self, "_runtime_status_heartbeat_interval_ms", 1000) or 1000)
            self._state_controller = RuntimeStateController(  # type: ignore[attr-defined]
                self.ws_manager,
                metrics_getter=lambda: self._metrics_controller.metrics,
                metrics_setter=self._metrics_controller.set_metrics,
                increment_counter_metric=lambda key, amount: self._increment_counter_metric(key, amount),
                heartbeat_interval_ms=heartbeat,
            )
        if not hasattr(self, "_output") or self._output is None:  # type: ignore[attr-defined]
            self._output = OutputFanoutController(  # type: ignore[attr-defined]
                self.ws_manager,
                obs_caption_output=getattr(self, "_obs_caption_output", None),
                state_controller=self._state_controller,  # type: ignore[arg-type]
            )
        # Enrich the broadcast state with live ws_manager diagnostics so the real-time
        # WebSocket payload carries accurate ws_events_* counters (otherwise these are
        # populated only on the HTTP status-polling path in runtime_service.py).
        ws_diag = self.ws_manager.diagnostics()  # type: ignore[attr-defined]
        broadcast_state = self._state.model_copy(  # type: ignore[attr-defined]
            update={
                "metrics": self._state.metrics.model_copy(  # type: ignore[attr-defined]
                    update={
                        "ws_events_connections_active": int(ws_diag.get("ws_events_connections_active", 0) or 0),
                        "ws_events_broadcast_count": int(ws_diag.get("ws_events_broadcast_count", 0) or 0),
                        "ws_events_send_failures": int(ws_diag.get("ws_events_send_failures", 0) or 0),
                        "ws_events_dead_connections_removed": int(ws_diag.get("ws_events_dead_connections_removed", 0) or 0),
                    }
                )
            }
        )
        await self._output.broadcast_runtime_update(broadcast_state)  # type: ignore[attr-defined]

    async def _broadcast_transcript(self, event: TranscriptEvent) -> None:
        await self._output.publish_transcript(event)

    async def _broadcast_transcript_segment_event(self, event: TranscriptEvent) -> None:
        await self._output.publish_transcript_segment_event(event)

    async def _broadcast_translation(self, event: TranslationEvent) -> None:
        await self._output.publish_translation(event)

    async def _publish_translation_dispatch_event(self, event: TranslationEvent) -> None:
        await self.subtitle_router.handle_translation(event)
        if self.subtitle_router.is_sequence_relevant_for_presentation(event.sequence):
            await self._broadcast_translation(event)
        await self._broadcast_runtime()

    async def _handle_obs_caption_payload(self, payload: SubtitlePayloadEvent) -> None:
        await self._output.publish_subtitle_payload(payload)

    def _handle_completed_export_record(self, record: dict) -> None:
        self._session.add_completed_export_record(record)

    def _export_session_files(self, *, stopped_at_utc: str) -> list[Path]:
        payload = self._session.build_session_export_payload(
            self.config_getter(),
            stopped_at_utc=stopped_at_utc,
        )
        if payload is None:
            return []

        session_row, records = payload
        base_filename = self._exporter.build_session_basename(
            session_started_at_utc=self._session.session_started_at_utc,
            session_id=str(self._session.session_id),
            profile=session_row["profile"],
        )
        return self._exporter.export_session(
            base_filename=base_filename,
            session_row=session_row,
            records=records,
        )

    async def apply_live_settings(self, config: dict) -> None:
        self._apply_vad_tuning()
        self._apply_recognition_processing_settings()
        self._translation.apply_live_settings()
        await self._output.apply_live_settings(config if isinstance(config, dict) else {})
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
            metrics=self._metrics_controller.metrics,
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
        previous = self._state
        previous_status = getattr(previous, "status", None)
        previous_running = getattr(previous, "is_running", None)
        if (
            previous_status != status
            or previous_running != is_running
            or (previous.last_error or None) != (last_error or None)
        ):
            from backend.core.pipeline_trace_log import pipeline_trace

            pipeline_trace(
                "runtime_state",
                "runtime_orchestrator",
                "state_changed",
                from_status=previous_status,
                to_status=status,
                from_is_running=previous_running,
                to_is_running=is_running,
                last_error=last_error,
                status_message=status_message,
            )
        self._state = self._build_runtime_state(
            is_running=is_running,
            status=status,
            started_at_utc=started_at_utc,
            last_error=last_error,
            status_message=status_message,
        )

    def _record_metrics(self, **values: float | int | None) -> None:
        self._metrics_controller.record(**values)

    def _runtime_material_status_snapshot(self, payload: dict[str, Any]) -> tuple[Any, ...]:
        return runtime_material_status_snapshot(payload)

    def _next_event_sequence(self, event_type: str) -> int:
        _ = event_type
        # Kept for backward-compat with callers; event sequencing is handled by RuntimeStateController.enrich().
        return 0

    def _enrich_event_payload(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._state_controller.enrich(event_type, payload)

    def _apply_translation_dispatcher_metrics(self, metrics: dict) -> None:
        self._metrics_controller.apply_translation_dispatcher_metrics(metrics)

    def _increment_metric(self, key: Literal["partial_updates_emitted", "finals_emitted", "suppressed_partial_updates"]) -> None:
        self._metrics_controller.increment_metric(key)

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
        self._metrics_controller.increment_counter_metric(key, amount)

    @staticmethod
    def _pcm16_rms_level(audio: bytes) -> float:
        return pcm16_rms_level(audio)
