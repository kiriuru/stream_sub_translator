from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.models import BrowserAsrDiagnostics


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrowserAsrGateway:
    def __init__(self, *, structured_logger: StructuredRuntimeLogger | None = None) -> None:
        self._state = BrowserAsrDiagnostics()
        self._structured_logger = structured_logger

    def reset(self) -> None:
        self._state = BrowserAsrDiagnostics()

    def worker_connected(self) -> None:
        self._state = self._state.model_copy(
            update={
                "worker_connected": True,
                "last_error": None,
            }
        )
        self._log_event(
            "browser_worker_connected",
            worker_connected=True,
            recognition_state=self._state.recognition_state,
            websocket_ready=self._state.websocket_ready,
        )

    def worker_disconnected(self) -> None:
        previous_state = self._state
        self._state = self._state.model_copy(
            update={
                "worker_connected": False,
                "recognition_running": False,
                "recognition_state": "disconnected",
                "websocket_ready": False,
            }
        )
        self._log_event(
            "browser_worker_disconnected",
            worker_connected=False,
            recognition_state="disconnected",
            desired_running=previous_state.desired_running,
            last_error=previous_state.last_error,
            degraded_reason=previous_state.degraded_reason,
        )

    def note_partial(self, *, text_len: int | None = None, source_lang: str | None = None, sequence: int | None = None) -> None:
        self._state = self._state.model_copy(update={"last_partial_at_utc": _utc_now(), "last_partial_age_ms": 0})
        self._log_event(
            "browser_external_partial",
            worker_connected=self._state.worker_connected,
            sequence=sequence,
            text_len=text_len,
            source_lang=source_lang,
            is_final=False,
        )

    def note_final(self, *, text_len: int | None = None, source_lang: str | None = None, sequence: int | None = None) -> None:
        self._state = self._state.model_copy(update={"last_final_at_utc": _utc_now(), "last_final_age_ms": 0})
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
            "desired_running": "desired_running",
            "recognition_running": "recognition_running",
            "websocket_ready": "websocket_ready",
        }
        for source_key, target_key in bool_fields.items():
            if source_key in payload:
                updates[target_key] = bool(payload.get(source_key))
        str_fields = {
            "recognition_state": "recognition_state",
            "last_error": "last_error",
            "degraded_reason": "degraded_reason",
            "visibility_state": "visibility_state",
            "reason": "last_status_reason",
            "error_type": "error_type",
        }
        for source_key, target_key in str_fields.items():
            if source_key in payload:
                raw_value = payload.get(source_key)
                updates[target_key] = str(raw_value).strip() or None
        int_fields = {
            "rearm_count": "rearm_count",
            "restart_count": "restart_count",
            "watchdog_rearm_count": "watchdog_rearm_count",
            "rearm_delay_ms": "last_rearm_delay_ms",
            "last_partial_age_ms": "last_partial_age_ms",
            "last_final_age_ms": "last_final_age_ms",
        }
        for source_key, target_key in int_fields.items():
            if source_key in payload:
                try:
                    updates[target_key] = max(0, int(payload.get(source_key) or 0))
                except (TypeError, ValueError):
                    continue
        if updates:
            self._state = self._state.model_copy(update=updates)
        reason = self._state.last_status_reason
        self._log_event(
            "browser_worker_status",
            worker_connected=self._state.worker_connected,
            desired_running=self._state.desired_running,
            recognition_running=self._state.recognition_running,
            recognition_state=self._state.recognition_state,
            websocket_ready=self._state.websocket_ready,
            visibility_state=self._state.visibility_state,
            rearm_count=self._state.rearm_count,
            watchdog_rearm_count=self._state.watchdog_rearm_count,
            rearm_delay_ms=self._state.last_rearm_delay_ms,
            last_partial_age_ms=self._state.last_partial_age_ms,
            last_final_age_ms=self._state.last_final_age_ms,
            error=self._state.last_error,
            error_type=self._state.error_type,
            reason=reason,
            degraded_reason=self._state.degraded_reason,
        )
        mapped_event = self._map_reason_to_event(reason)
        if mapped_event is not None:
            self._log_event(
                mapped_event,
                worker_connected=self._state.worker_connected,
                desired_running=self._state.desired_running,
                recognition_state=self._state.recognition_state,
                visibility_state=self._state.visibility_state,
                rearm_count=self._state.rearm_count,
                watchdog_rearm_count=self._state.watchdog_rearm_count,
                rearm_delay_ms=self._state.last_rearm_delay_ms,
                error=self._state.last_error,
                error_type=self._state.error_type,
                degraded_reason=self._state.degraded_reason,
            )
        if self._state.last_error and (
            reason in {"recognition-error", "terminal-error", "microphone-permission-failed"}
            or previous_state.last_error != self._state.last_error
        ):
            self._log_event(
                "browser_error",
                error=self._state.last_error,
                error_type=self._state.error_type,
                recognition_state=self._state.recognition_state,
                visibility_state=self._state.visibility_state,
                worker_connected=self._state.worker_connected,
            )
        if self._state.degraded_reason and previous_state.degraded_reason != self._state.degraded_reason:
            self._log_event(
                "browser_degraded",
                degraded_reason=self._state.degraded_reason,
                desired_running=self._state.desired_running,
                recognition_state=self._state.recognition_state,
                visibility_state=self._state.visibility_state,
                worker_connected=self._state.worker_connected,
            )

    def diagnostics(self) -> BrowserAsrDiagnostics:
        return self._state.model_copy()

    @staticmethod
    def _map_reason_to_event(reason: str | None) -> str | None:
        mapping = {
            "start-requested": "browser_recognition_start_requested",
            "recognition-started": "browser_recognition_started",
            "recognition-ended": "browser_onend",
            "recognition-error": "browser_onerror",
            "restart-scheduled": "browser_rearm_scheduled",
            "restart-executed": "browser_rearm_executed",
            "watchdog-rearm": "browser_watchdog_rearm",
            "visibility": "browser_visibility_changed",
        }
        normalized = str(reason or "").strip().lower()
        return mapping.get(normalized)

    def _log_event(self, event: str, **fields: Any) -> None:
        if self._structured_logger is None:
            return
        self._structured_logger.log(
            "browser_recognition",
            event,
            source="browser_asr_gateway",
            payload=fields,
        )
