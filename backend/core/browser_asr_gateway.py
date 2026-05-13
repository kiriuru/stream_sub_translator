from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.models import BrowserAsrDiagnostics


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrowserAsrGateway:
    _EXPERIMENTAL_BROWSER_MODE = "browser_google_experimental"
    _ROUTINE_RESTART_EVENTS = {
        "browser_recognition_started",
        "browser_onend",
        "browser_rearm_scheduled",
        "browser_rearm_executed",
        "recognition_onstart",
        "recognition_onend",
        "experimental_rearm_scheduled",
        "experimental_rearm_executed",
    }
    _NOISY_ERROR_TYPES = {"no-speech"}
    _ROUTINE_LOG_SAMPLE_EVERY = 25
    _ROUTINE_LOG_VERBOSE_LIMIT = 3
    # Structured runtime log: avoid writing on every worker status tick (can be sub-second).
    _STATUS_HEARTBEAT_INTERVAL_MS = 15000
    # When only high-churn fields change (RMS, result index, duplicate counters, …), avoid
    # spamming runtime-events; operational state transitions still log immediately.
    _DETAIL_ONLY_STATUS_LOG_MIN_INTERVAL_MS = 3600

    def __init__(self, *, structured_logger: StructuredRuntimeLogger | None = None) -> None:
        self._state = BrowserAsrDiagnostics()
        self._structured_logger = structured_logger
        self._last_status_heartbeat_at_ms = 0
        self._last_browser_worker_status_log_ms = 0
        self._heartbeat_counter_baseline = self._counter_snapshot(self._state)

    def reset(self) -> None:
        self._state = BrowserAsrDiagnostics()
        self._last_status_heartbeat_at_ms = 0
        self._last_browser_worker_status_log_ms = 0
        self._heartbeat_counter_baseline = self._counter_snapshot(self._state)

    def worker_connected(self, *, browser_mode: str | None = None) -> None:
        normalized_mode = self._normalize_browser_mode(browser_mode) or self._state.browser_mode
        experimental = normalized_mode == self._EXPERIMENTAL_BROWSER_MODE
        self._state = self._state.model_copy(
            update={
                "worker_connected": True,
                "browser_mode": normalized_mode,
                "provider_name": normalized_mode,
                "experimental": experimental,
                "last_error": None,
            }
        )
        self._log_event(
            "browser_worker_connected",
            worker_connected=True,
            browser_mode=self._state.browser_mode,
            experimental=self._state.experimental,
            recognition_state=self._state.recognition_state,
            websocket_ready=self._state.websocket_ready,
        )
        if self._state.experimental:
            self._log_event(
                "experimental_worker_loaded",
                worker_connected=True,
                browser_mode=self._state.browser_mode,
                experimental=True,
                recognition_state=self._state.recognition_state,
                websocket_ready=self._state.websocket_ready,
            )

    def worker_disconnected(self, *, browser_mode: str | None = None) -> None:
        previous_state = self._state
        normalized_mode = self._normalize_browser_mode(browser_mode) or previous_state.browser_mode
        experimental = normalized_mode == self._EXPERIMENTAL_BROWSER_MODE or previous_state.experimental
        self._state = self._state.model_copy(
            update={
                "worker_connected": False,
                "browser_mode": normalized_mode,
                "provider_name": normalized_mode,
                "experimental": experimental,
                "recognition_running": False,
                "recognition_state": "disconnected",
                "websocket_ready": False,
            }
        )
        self._log_event(
            "browser_worker_disconnected",
            worker_connected=False,
            browser_mode=self._state.browser_mode,
            experimental=self._state.experimental,
            recognition_state="disconnected",
            desired_running=previous_state.desired_running,
            last_error=previous_state.last_error,
            degraded_reason=previous_state.degraded_reason,
        )

    def note_partial(self, *, text_len: int | None = None, source_lang: str | None = None, sequence: int | None = None) -> None:
        _ = (text_len, source_lang, sequence)
        self._state = self._state.model_copy(
            update={
                "last_partial_at_utc": _utc_now(),
                "last_partial_age_ms": 0,
                "browser_session_age_ms": self._state.browser_session_age_ms,
            }
        )
        # Do not log each partial to runtime-events.log — streaming partials can generate
        # very high line rates and megabytes per hour. Timestamps above feed runtime/diagnostics.

    def note_final(self, *, text_len: int | None = None, source_lang: str | None = None, sequence: int | None = None) -> None:
        self._state = self._state.model_copy(
            update={
                "last_final_at_utc": _utc_now(),
                "last_final_age_ms": 0,
                "browser_session_age_ms": self._state.browser_session_age_ms,
            }
        )
        self._log_event(
            "browser_external_final",
            worker_connected=self._state.worker_connected,
            sequence=sequence,
            text_len=text_len,
            source_lang=source_lang,
            is_final=True,
        )

    def update_status(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        previous_state = self._state
        updates: dict[str, Any] = {}
        bool_fields = {
            "experimental": "experimental",
            "desired_running": "desired_running",
            "pending_start": "pending_start",
            "recognition_running": "recognition_running",
            "recognition_continuous": "recognition_continuous",
            "websocket_ready": "websocket_ready",
            "forced_final": "forced_final",
            "active_recognition": "active_recognition",
            "active_media_stream": "active_media_stream",
            "browser_cycle_pending": "browser_cycle_pending",
            "mic_stream_active": "mic_stream_active",
            "audio_track_enabled": "audio_track_enabled",
            "audio_track_live": "audio_track_live",
            "audio_track_muted": "audio_track_muted",
            "audio_track_reused": "audio_track_reused",
            "fallback_to_default_start": "fallback_to_default_start",
            "fallback_used": "fallback_used",
        }
        for source_key, target_key in bool_fields.items():
            if source_key in payload:
                updates[target_key] = bool(payload.get(source_key))
        str_fields = {
            "browser_mode": "browser_mode",
            "start_mode": "start_mode",
            "recognition_state": "recognition_state",
            "browser_supervisor_state": "supervisor_state",
            "supervisor_state": "supervisor_state",
            "effective_continuous_mode": "effective_continuous_mode",
            "provider_name": "provider_name",
            "last_error": "last_error",
            "last_start_error": "last_start_error",
            "last_audio_track_error": "last_audio_track_error",
            "get_user_media_last_error": "get_user_media_last_error",
            "degraded_reason": "degraded_reason",
            "visibility_state": "visibility_state",
            "reason": "last_status_reason",
            "error_type": "error_type",
            "audio_track_kind": "audio_track_kind",
            "audio_track_ready_state": "audio_track_ready_state",
            "session_id": "session_id",
            "client_segment_id": "client_segment_id",
            "mic_track_ready_state": "mic_track_ready_state",
        }
        for source_key, target_key in str_fields.items():
            if source_key in payload:
                raw_value = payload.get(source_key)
                normalized_value = str(raw_value).strip() or None
                if source_key == "browser_mode":
                    normalized_value = self._normalize_browser_mode(normalized_value)
                    if normalized_value == self._EXPERIMENTAL_BROWSER_MODE:
                        updates["experimental"] = True
                updates[target_key] = normalized_value
        int_fields = {
            "rearm_count": "rearm_count",
            "restart_count": "restart_count",
            "watchdog_rearm_count": "watchdog_rearm_count",
            "rearm_delay_ms": "last_rearm_delay_ms",
            "last_partial_age_ms": "last_partial_age_ms",
            "last_final_age_ms": "last_final_age_ms",
            "audio_track_reopen_count": "audio_track_reopen_count",
            "audio_track_start_attempts": "audio_track_start_attempts",
            "audio_track_start_failures": "audio_track_start_failures",
            "generation_id": "generation_id",
            "no_speech_count": "no_speech_count",
            "network_error_count": "network_error_count",
            "last_result_index": "last_result_index",
            "last_result_at_ms": "last_result_at_ms",
            "last_session_started_at_ms": "last_session_started_at_ms",
            "last_session_ended_at_ms": "last_session_ended_at_ms",
            "browser_session_age_ms": "browser_session_age_ms",
            "browser_cycle_count": "browser_cycle_count",
            "browser_minimum_reconnect_suppressed_count": "browser_minimum_reconnect_suppressed_count",
            "browser_forced_final_on_interruption_count": "browser_forced_final_on_interruption_count",
            "duplicate_partial_suppressed": "duplicate_partial_suppressed",
            "duplicate_final_suppressed": "duplicate_final_suppressed",
            "late_forced_final_suppressed": "late_forced_final_suppressed",
            "mic_active_recent_ms": "mic_active_recent_ms",
            "last_mic_activity_at": "last_mic_activity_at",
            "get_user_media_count": "get_user_media_count",
            "media_tracks_stopped_count": "media_tracks_stopped_count",
            "media_track_leak_guard_count": "media_track_leak_guard_count",
            "stopping_since_ms": "stopping_since_ms",
            "last_seen_at_ms": "last_seen_at_ms",
            "stale_worker_events_ignored": "stale_worker_events_ignored",
        }
        for source_key, target_key in int_fields.items():
            if source_key in payload:
                try:
                    updates[target_key] = max(0, int(payload.get(source_key) or 0))
                except (TypeError, ValueError):
                    continue
        if "mic_rms" in payload:
            try:
                updates["mic_rms"] = max(0.0, float(payload.get("mic_rms") or 0.0))
            except (TypeError, ValueError):
                pass
        if updates:
            self._state = self._state.model_copy(update=updates)
        reason = self._state.last_status_reason
        mapped_event = self._map_reason_to_event(reason)
        if self._should_log_status_snapshot(previous_state=previous_state, reason=reason, mapped_event=mapped_event):
            self._log_event("browser_worker_status", **self._structured_status_log_summary(reason))
            self._last_browser_worker_status_log_ms = self._now_ms()
            self._mark_status_activity()
        elif self._should_log_status_heartbeat():
            self._log_event("browser_worker_heartbeat", **self._heartbeat_payload())
            self._mark_status_activity()
        if mapped_event is not None and self._should_log_mapped_event(mapped_event):
            self._log_event(mapped_event, **self._structured_mapped_event_log_summary())
        if self._state.last_error and (
            reason in {"recognition-error", "terminal-error", "microphone-permission-failed"}
            or previous_state.last_error != self._state.last_error
        ) and self._should_log_error_event():
            self._log_event(
                "browser_error",
                error=self._state.last_error,
                error_type=self._state.error_type,
                browser_mode=self._state.browser_mode,
                experimental=self._state.experimental,
                start_mode=self._state.start_mode,
                recognition_state=self._state.recognition_state,
                visibility_state=self._state.visibility_state,
                worker_connected=self._state.worker_connected,
            )
        if self._state.degraded_reason and previous_state.degraded_reason != self._state.degraded_reason:
            self._log_event(
                "experimental_degraded" if self._state.experimental else "browser_degraded",
                browser_mode=self._state.browser_mode,
                experimental=self._state.experimental,
                start_mode=self._state.start_mode,
                degraded_reason=self._state.degraded_reason,
                desired_running=self._state.desired_running,
                recognition_state=self._state.recognition_state,
                visibility_state=self._state.visibility_state,
                worker_connected=self._state.worker_connected,
            )

    def diagnostics(self) -> BrowserAsrDiagnostics:
        return self._state.model_copy()

    def _structured_status_log_summary(self, reason: str | None) -> dict[str, Any]:
        """Small payload for runtime-events.log; full state remains in diagnostics / runtime API."""
        s = self._state
        return {
            "reason": reason,
            "worker_connected": s.worker_connected,
            "browser_mode": s.browser_mode,
            "experimental": s.experimental,
            "desired_running": s.desired_running,
            "recognition_running": s.recognition_running,
            "recognition_state": s.recognition_state,
            "supervisor_state": s.supervisor_state,
            "websocket_ready": s.websocket_ready,
            "provider_name": s.provider_name,
            "start_mode": s.start_mode,
            "generation_id": s.generation_id,
            "session_id": s.session_id,
            "client_segment_id": s.client_segment_id,
            "visibility_state": s.visibility_state,
            "rearm_count": s.rearm_count,
            "watchdog_rearm_count": s.watchdog_rearm_count,
            "error_type": s.error_type,
            "last_error": s.last_error,
            "degraded_reason": s.degraded_reason,
        }

    def _structured_mapped_event_log_summary(self) -> dict[str, Any]:
        s = self._state
        return {
            "recognition_state": s.recognition_state,
            "supervisor_state": s.supervisor_state,
            "generation_id": s.generation_id,
            "session_id": s.session_id,
            "client_segment_id": s.client_segment_id,
            "rearm_count": s.rearm_count,
            "error_type": s.error_type,
            "visibility_state": s.visibility_state,
        }

    def _map_reason_to_event(self, reason: str | None) -> str | None:
        mapping = {
            "start-requested": "browser_recognition_start_requested",
            "recognition-started": "recognition_onstart" if self._state.experimental else "browser_recognition_started",
            "recognition-ended": "recognition_onend" if self._state.experimental else "browser_onend",
            "recognition-error": "recognition_onerror" if self._state.experimental else "browser_onerror",
            "restart-scheduled": "experimental_rearm_scheduled" if self._state.experimental else "browser_rearm_scheduled",
            "restart-executed": "experimental_rearm_executed" if self._state.experimental else "browser_rearm_executed",
            "watchdog-rearm": "experimental_watchdog_rearm" if self._state.experimental else "browser_watchdog_rearm",
            "visibility": "browser_visibility_changed",
            "user-stop": "experimental_stop" if self._state.experimental else None,
            "audio-track-permission-requested": "audio_track_permission_requested",
            "audio-track-permission-granted": "audio_track_permission_granted",
            "audio-track-permission-denied": "audio_track_permission_denied",
            "audio-track-opened": "audio_track_opened",
            "audio-track-reused": "audio_track_reused",
            "audio-track-ended": "audio_track_ended",
            "audio-track-muted": "audio_track_muted",
            "audio-track-unmuted": "audio_track_unmuted",
            "audio-track-start-attempt": "audio_track_start_attempt",
            "audio-track-start-success": "audio_track_start_success",
            "audio-track-start-failed": "audio_track_start_failed",
            "fallback-default-start-attempt": "fallback_default_start_attempt",
            "fallback-default-start-success": "fallback_default_start_success",
            "fallback-default-start-failed": "fallback_default_start_failed",
            "experimental-worker-loaded": "experimental_worker_loaded",
        }
        normalized = str(reason or "").strip().lower()
        return mapping.get(normalized)

    def _should_log_status_snapshot(
        self,
        *,
        previous_state: BrowserAsrDiagnostics,
        reason: str | None,
        mapped_event: str | None,
    ) -> bool:
        if mapped_event is not None or reason == "degraded":
            return False
        if reason in {"socket-open", "user-stop", "terminal-error", "microphone-permission-failed"}:
            return True
        prev_core = self._core_status_snapshot(previous_state)
        cur_core = self._core_status_snapshot(self._state)
        if prev_core != cur_core:
            return True
        prev_mat = self._material_status_snapshot(previous_state)
        cur_mat = self._material_status_snapshot(self._state)
        if prev_mat == cur_mat:
            return False
        return (self._now_ms() - self._last_browser_worker_status_log_ms) >= int(
            self._DETAIL_ONLY_STATUS_LOG_MIN_INTERVAL_MS
        )

    def _core_status_snapshot(self, state: BrowserAsrDiagnostics) -> tuple[Any, ...]:
        """Subset of fields that reflect user-observable / supervisor behavior (not per-tick RMS or result cursor)."""
        return (
            state.worker_connected,
            state.desired_running,
            state.recognition_running,
            state.recognition_state,
            state.supervisor_state,
            state.websocket_ready,
            state.browser_mode,
            state.start_mode,
            state.provider_name,
            state.session_id,
            state.client_segment_id,
            state.generation_id,
            state.active_recognition,
            state.active_media_stream,
            state.pending_start,
            state.effective_continuous_mode,
            state.recognition_continuous,
            state.forced_final,
            state.last_session_started_at_ms,
            state.last_session_ended_at_ms,
            state.browser_cycle_pending,
            state.browser_cycle_count,
            state.browser_minimum_reconnect_suppressed_count,
            state.browser_forced_final_on_interruption_count,
            state.mic_track_ready_state,
            state.mic_track_muted,
            state.get_user_media_last_error,
            state.mic_stream_active,
            state.audio_track_live,
            state.audio_track_ready_state,
            state.audio_track_muted,
            state.fallback_used,
            state.visibility_state,
            state.last_error,
            state.error_type,
            state.degraded_reason,
            state.rearm_count,
            state.restart_count,
            state.watchdog_rearm_count,
            state.stopping_since_ms,
        )

    def _material_status_snapshot(self, state: BrowserAsrDiagnostics) -> tuple[Any, ...]:
        return (
            state.worker_connected,
            state.desired_running,
            state.recognition_running,
            state.recognition_state,
            state.supervisor_state,
            state.websocket_ready,
            state.browser_mode,
            state.start_mode,
            state.provider_name,
            state.session_id,
            state.client_segment_id,
            state.generation_id,
            state.active_recognition,
            state.active_media_stream,
            state.pending_start,
            state.effective_continuous_mode,
            state.recognition_continuous,
            state.forced_final,
            state.last_result_index,
            state.last_session_started_at_ms,
            state.last_session_ended_at_ms,
            state.browser_cycle_pending,
            state.browser_cycle_count,
            state.browser_minimum_reconnect_suppressed_count,
            state.browser_forced_final_on_interruption_count,
            state.duplicate_partial_suppressed,
            state.duplicate_final_suppressed,
            state.late_forced_final_suppressed,
            state.mic_track_ready_state,
            state.mic_track_muted,
            state.mic_rms,
            state.get_user_media_count,
            state.get_user_media_last_error,
            state.mic_stream_active,
            state.media_tracks_stopped_count,
            state.media_track_leak_guard_count,
            state.audio_track_live,
            state.audio_track_ready_state,
            state.audio_track_muted,
            state.fallback_used,
            state.visibility_state,
            state.last_error,
            state.error_type,
            state.degraded_reason,
            state.no_speech_count,
            state.network_error_count,
            state.stale_worker_events_ignored,
        )

    def _should_log_status_heartbeat(self) -> bool:
        if not (self._state.worker_connected or self._state.desired_running):
            return False
        return (self._now_ms() - self._last_status_heartbeat_at_ms) >= self._STATUS_HEARTBEAT_INTERVAL_MS

    def _heartbeat_payload(self) -> dict[str, Any]:
        current_counters = self._counter_snapshot(self._state)
        previous_counters = self._heartbeat_counter_baseline
        counters_delta = {
            key: value - previous_counters.get(key, 0)
            for key, value in current_counters.items()
            if (value - previous_counters.get(key, 0)) != 0
        }
        return {
            "state": self._state.recognition_state or self._state.supervisor_state or "idle",
            "generation_id": self._state.generation_id,
            "last_result_age_ms": self._last_result_age_ms(),
            "counters_delta": counters_delta,
        }

    def _mark_status_activity(self) -> None:
        self._last_status_heartbeat_at_ms = self._now_ms()
        self._heartbeat_counter_baseline = self._counter_snapshot(self._state)

    def _last_result_age_ms(self) -> int | None:
        ages = [age for age in (self._state.last_partial_age_ms, self._state.last_final_age_ms) if age is not None]
        if not ages:
            return None
        return min(ages)

    @staticmethod
    def _counter_snapshot(state: BrowserAsrDiagnostics) -> dict[str, int]:
        return {
            "rearm_count": max(0, int(state.rearm_count or 0)),
            "restart_count": max(0, int(state.restart_count or 0)),
            "watchdog_rearm_count": max(0, int(state.watchdog_rearm_count or 0)),
            "no_speech_count": max(0, int(state.no_speech_count or 0)),
            "network_error_count": max(0, int(state.network_error_count or 0)),
            "duplicate_partial_suppressed": max(0, int(state.duplicate_partial_suppressed or 0)),
            "duplicate_final_suppressed": max(0, int(state.duplicate_final_suppressed or 0)),
            "late_forced_final_suppressed": max(0, int(state.late_forced_final_suppressed or 0)),
            "stale_worker_events_ignored": max(0, int(state.stale_worker_events_ignored or 0)),
        }

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    def _should_log_mapped_event(self, event: str) -> bool:
        if event in self._ROUTINE_RESTART_EVENTS:
            return self._should_sample_routine_cycle()
        if event == "browser_onerror" and self._state.error_type in self._NOISY_ERROR_TYPES:
            return self._should_sample_routine_cycle()
        return True

    def _should_log_error_event(self) -> bool:
        if self._state.error_type in self._NOISY_ERROR_TYPES:
            return self._should_sample_routine_cycle()
        return True

    def _should_sample_routine_cycle(self) -> bool:
        if self._state.degraded_reason:
            return True
        rearm_count = max(0, int(self._state.rearm_count or 0))
        if rearm_count <= self._ROUTINE_LOG_VERBOSE_LIMIT:
            return True
        return rearm_count % self._ROUTINE_LOG_SAMPLE_EVERY == 0

    def _log_event(self, event: str, **fields: Any) -> None:
        if self._structured_logger is None:
            return
        self._structured_logger.log(
            self._log_channel(),
            event,
            source="browser_asr_gateway",
            payload=fields,
        )

    def _log_channel(self) -> str:
        if self._state.experimental or self._state.browser_mode == self._EXPERIMENTAL_BROWSER_MODE:
            return "browser_recognition_experimental"
        return "browser_recognition"

    @staticmethod
    def _normalize_browser_mode(raw_value: str | None) -> str | None:
        normalized = str(raw_value or "").strip().lower()
        if normalized in {"browser_google", "browser_google_experimental"}:
            return normalized
        return None
