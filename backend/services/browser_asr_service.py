from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import FastAPI, WebSocket

from backend.core.runtime.browser_asr_replay import BrowserAsrJsonlRecorder
from backend.core.runtime.browser_asr_trace import BrowserAsrTraceFields, log_basr, new_event_id
from backend.core.timekeeping import perf_counter_clock


class BrowserAsrService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app
        self._lock = asyncio.Lock()
        self._active_transport_id = 0
        self._active_websocket: WebSocket | None = None
        self._active_client_session_id: str | None = None
        self._active_generation_id: int = 0
        self._clock = perf_counter_clock
        self._jsonl_recorder = BrowserAsrJsonlRecorder.from_env()
        self._snapshot: dict[str, Any] = {
            "worker_connected": False,
            "recognition_state": "disconnected",
            "supervisor_state": "idle",
            "desired_running": False,
            "degraded_reason": None,
            "last_error": None,
            "last_seen_at_ms": None,
            "session_id": None,
            "generation_id": 0,
            "client_segment_id": None,
            "forced_final": False,
            "provider_name": None,
            "active_recognition": False,
            "active_media_stream": False,
            "last_result_index": None,
            "last_result_at_ms": None,
            "last_session_started_at_ms": None,
            "last_session_ended_at_ms": None,
            "browser_session_age_ms": None,
            "browser_cycle_pending": False,
            "browser_cycle_count": 0,
            "browser_minimum_reconnect_suppressed_count": 0,
            "browser_forced_final_on_interruption_count": 0,
            "browser_restarts_count": 0,
            "browser_no_speech_count": 0,
            "browser_network_error_count": 0,
            "duplicate_partial_suppressed": 0,
            "duplicate_final_suppressed": 0,
            "late_forced_final_suppressed": 0,
            "mic_track_ready_state": None,
            "mic_track_muted": False,
            "mic_rms": 0.0,
            "mic_active_recent_ms": None,
            "last_mic_activity_at": None,
            "get_user_media_count": 0,
            "get_user_media_last_error": None,
            "mic_stream_active": False,
            "media_tracks_stopped_count": 0,
            "media_track_leak_guard_count": 0,
            "browser_stale_events_ignored": 0,
        }

    @property
    def _structured_logger(self):
        return getattr(self._app.state, "structured_runtime_logger", None)

    @property
    def _runtime_orchestrator(self):
        return self._app.state.runtime_orchestrator

    async def register_connection(self, websocket: WebSocket) -> int:
        async with self._lock:
            self._active_transport_id += 1
            transport_id = self._active_transport_id
            self._active_websocket = websocket
            self._snapshot.update(
                {
                    "worker_connected": True,
                    "recognition_state": "idle",
                    "supervisor_state": "idle",
                    "client_segment_id": None,
                    "forced_final": False,
                    "provider_name": None,
                    "active_recognition": False,
                    "active_media_stream": False,
                    "duplicate_partial_suppressed": 0,
                    "duplicate_final_suppressed": 0,
                    "late_forced_final_suppressed": 0,
                    "mic_track_ready_state": None,
                    "mic_track_muted": False,
                    "mic_rms": 0.0,
                    "mic_active_recent_ms": None,
                    "last_mic_activity_at": None,
                    "get_user_media_count": 0,
                    "get_user_media_last_error": None,
                    "mic_stream_active": False,
                    "media_tracks_stopped_count": 0,
                    "media_track_leak_guard_count": 0,
                    "last_seen_at_ms": self._now_ms(),
                }
            )
            return transport_id

    async def disconnect(self, transport_id: int) -> None:
        async with self._lock:
            if transport_id != self._active_transport_id:
                return
            self._active_websocket = None
            self._snapshot.update(
                {
                    "worker_connected": False,
                    "recognition_state": "disconnected",
                    "supervisor_state": "idle",
                    "desired_running": False,
                    "client_segment_id": None,
                    "forced_final": False,
                    "active_recognition": False,
                    "active_media_stream": False,
                    "last_seen_at_ms": self._now_ms(),
                }
            )
        await self._runtime_orchestrator.browser_asr_worker_disconnected()

    async def worker_connected(self) -> None:
        await self._runtime_orchestrator.browser_asr_worker_connected()

    async def handle_status(self, transport_id: int, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        accepted, reject_code = await self._accept_payload(transport_id, payload)
        if not accepted:
            self._log_transport_reject(reject_code, transport_id, payload)
            return False
        snapshot_update = {
            "worker_connected": True,
            "recognition_state": str(payload.get("recognition_state", self._snapshot["recognition_state"]) or "idle"),
            "supervisor_state": str(payload.get("browser_supervisor_state", payload.get("supervisor_state", "idle")) or "idle"),
            "desired_running": bool(payload.get("desired_running", False)),
            "degraded_reason": payload.get("degraded_reason"),
            "last_error": payload.get("last_error"),
            "last_seen_at_ms": self._now_ms(),
            "provider_name": str(payload.get("provider_name", self._snapshot["provider_name"]) or "").strip() or None,
            "generation_id": int(payload.get("generation_id", self._snapshot["generation_id"]) or 0),
            "session_id": str(payload.get("session_id", self._snapshot["session_id"]) or "").strip() or None,
            "client_segment_id": str(payload.get("client_segment_id", self._snapshot["client_segment_id"]) or "").strip() or None,
            "forced_final": bool(payload.get("forced_final", self._snapshot["forced_final"])),
            "active_recognition": bool(payload.get("active_recognition", self._snapshot["active_recognition"])),
            "active_media_stream": bool(payload.get("active_media_stream", self._snapshot["active_media_stream"])),
            "last_result_index": (
                int(payload.get("last_result_index", self._snapshot["last_result_index"]) or 0)
                if payload.get("last_result_index") is not None
                else None
            ),
            "last_result_at_ms": (
                max(0, int(payload.get("last_result_at_ms", 0) or 0))
                if payload.get("last_result_at_ms") is not None
                else None
            ),
            "last_session_started_at_ms": (
                max(0, int(payload.get("last_session_started_at_ms", 0) or 0))
                if payload.get("last_session_started_at_ms") is not None
                else None
            ),
            "last_session_ended_at_ms": (
                max(0, int(payload.get("last_session_ended_at_ms", 0) or 0))
                if payload.get("last_session_ended_at_ms") is not None
                else None
            ),
            "browser_session_age_ms": (
                max(0, int(payload.get("browser_session_age_ms", 0) or 0))
                if payload.get("browser_session_age_ms") is not None
                else None
            ),
            "browser_cycle_pending": bool(
                payload.get("browser_cycle_pending", self._snapshot["browser_cycle_pending"])
            ),
            "browser_cycle_count": int(payload.get("browser_cycle_count", self._snapshot["browser_cycle_count"]) or 0),
            "browser_minimum_reconnect_suppressed_count": int(
                payload.get(
                    "browser_minimum_reconnect_suppressed_count",
                    self._snapshot["browser_minimum_reconnect_suppressed_count"],
                )
                or 0
            ),
            "browser_forced_final_on_interruption_count": int(
                payload.get(
                    "browser_forced_final_on_interruption_count",
                    self._snapshot["browser_forced_final_on_interruption_count"],
                )
                or 0
            ),
            "browser_restarts_count": int(payload.get("restart_count", self._snapshot["browser_restarts_count"]) or 0),
            "browser_no_speech_count": int(payload.get("no_speech_count", self._snapshot["browser_no_speech_count"]) or 0),
            "browser_network_error_count": int(payload.get("network_error_count", self._snapshot["browser_network_error_count"]) or 0),
            "duplicate_partial_suppressed": int(
                payload.get("duplicate_partial_suppressed", self._snapshot["duplicate_partial_suppressed"]) or 0
            ),
            "duplicate_final_suppressed": int(
                payload.get("duplicate_final_suppressed", self._snapshot["duplicate_final_suppressed"]) or 0
            ),
            "late_forced_final_suppressed": int(
                payload.get("late_forced_final_suppressed", self._snapshot["late_forced_final_suppressed"]) or 0
            ),
            "mic_track_ready_state": str(
                payload.get("mic_track_ready_state", self._snapshot["mic_track_ready_state"]) or ""
            ).strip()
            or None,
            "mic_track_muted": bool(payload.get("mic_track_muted", self._snapshot["mic_track_muted"])),
            "mic_rms": float(payload.get("mic_rms", self._snapshot["mic_rms"]) or 0.0),
            "mic_active_recent_ms": (
                max(0, int(payload.get("mic_active_recent_ms", 0) or 0))
                if payload.get("mic_active_recent_ms") is not None
                else None
            ),
            "last_mic_activity_at": (
                max(0, int(payload.get("last_mic_activity_at", 0) or 0))
                if payload.get("last_mic_activity_at") is not None
                else None
            ),
            "get_user_media_count": int(payload.get("get_user_media_count", self._snapshot["get_user_media_count"]) or 0),
            "get_user_media_last_error": str(
                payload.get("get_user_media_last_error", self._snapshot["get_user_media_last_error"]) or ""
            ).strip()
            or None,
            "mic_stream_active": bool(payload.get("mic_stream_active", self._snapshot["mic_stream_active"])),
            "media_tracks_stopped_count": int(
                payload.get("media_tracks_stopped_count", self._snapshot["media_tracks_stopped_count"]) or 0
            ),
            "media_track_leak_guard_count": int(
                payload.get("media_track_leak_guard_count", self._snapshot["media_track_leak_guard_count"]) or 0
            ),
        }
        async with self._lock:
            self._snapshot.update(snapshot_update)
        payload_for_orchestrator = dict(payload)
        payload_for_orchestrator["basr_status_event_id"] = new_event_id()
        payload_for_orchestrator["basr_status_mono"] = self._clock()
        payload_for_orchestrator["basr_transport_id"] = transport_id
        await self._runtime_orchestrator.update_browser_asr_worker_status(payload_for_orchestrator)
        return True

    async def handle_external_update(self, transport_id: int, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        accepted, reject_code = await self._accept_payload(transport_id, payload)
        if not accepted:
            self._log_transport_reject(reject_code, transport_id, payload)
            self._jsonl_recorder.maybe_record(
                {
                    "kind": "ingress_reject",
                    "reject_code": reject_code,
                    "transport_id": transport_id,
                    "advance_mono": 0.0,
                }
            )
            return False
        backend_received_at_ms = self._now_ms()
        mono = self._clock()
        event_id = new_event_id()
        client_parent = str(payload.get("client_event_id") or "").strip() or None
        update_payload: dict[str, Any] = {
            "partial": str(payload.get("partial", "") or ""),
            "final": str(payload.get("final", "") or ""),
            "is_final": bool(payload.get("is_final", False)),
            "source_lang": str(payload.get("source_lang", "") or "") or None,
            "generation_id": int(payload.get("generation_id", 0) or 0),
            "session_id": str(payload.get("session_id", "") or "").strip() or None,
            "client_segment_id": str(payload.get("client_segment_id", "") or "").strip() or None,
            "forced_final": bool(payload.get("forced_final", False)),
            "asr_operational_event_id": event_id,
            "causal_parent_asr_event_id": client_parent,
            "basr_mono_ingress_at": mono,
            "transport_id": transport_id,
        }
        if payload.get("asr_result_created_at_ms") is not None:
            update_payload["asr_result_created_at_ms"] = int(payload.get("asr_result_created_at_ms", 0) or 0)
        if payload.get("worker_send_started_at_ms") is not None:
            update_payload["worker_send_started_at_ms"] = int(payload.get("worker_send_started_at_ms", 0) or 0)
        if payload.get("worker_message_sequence") is not None:
            update_payload["worker_message_sequence"] = int(payload.get("worker_message_sequence", 0) or 0)
        if any(
            key in update_payload
            for key in ("asr_result_created_at_ms", "worker_send_started_at_ms", "worker_message_sequence")
        ):
            update_payload["backend_received_at_ms"] = backend_received_at_ms
        await self._runtime_orchestrator.ingest_external_asr_update(**update_payload)
        self._jsonl_recorder.maybe_record(
            {
                "kind": "ingest",
                "event_id": event_id,
                "causal_parent_id": client_parent,
                "generation_id": update_payload["generation_id"],
                "session_id": update_payload["session_id"],
                "transport_id": transport_id,
                "mono_ingress_at": mono,
                "is_final": update_payload["is_final"],
                "advance_mono": 0.0,
            }
        )
        async with self._lock:
            self._snapshot["last_seen_at_ms"] = self._now_ms()
        return True

    async def send_control(self, action: str, *, reason: str | None = None) -> bool:
        async with self._lock:
            websocket = self._active_websocket
            transport_id = self._active_transport_id
        if websocket is None:
            return False
        try:
            await websocket.send_json(
                {
                    "type": "browser_asr_control",
                    "action": str(action or "").strip().lower() or "noop",
                    "reason": str(reason or "").strip() or None,
                    "issued_at_ms": self._now_ms(),
                    "transport_id": transport_id,
                }
            )
            return True
        except Exception:
            await self.disconnect(transport_id)
            return False

    def diagnostics(self) -> dict[str, Any]:
        snapshot = dict(self._snapshot)
        last_seen_at_ms = snapshot.get("last_seen_at_ms")
        snapshot["browser_worker_last_seen_age_ms"] = (
            max(0, self._now_ms() - int(last_seen_at_ms))
            if isinstance(last_seen_at_ms, int)
            else None
        )
        snapshot["browser_worker_generation"] = snapshot.get("generation_id", 0)
        return snapshot

    def has_active_transport(self) -> bool:
        return self._active_websocket is not None

    def _log_transport_reject(self, code: str | None, transport_id: int, payload: dict[str, Any]) -> None:
        trace = BrowserAsrTraceFields(
            event_id=new_event_id(),
            causal_parent_id=None,
            generation_id=int(payload.get("generation_id", 0) or 0) or None,
            session_id=str(payload.get("session_id", "") or "").strip() or None,
            transport_id=transport_id,
            mono_ingress_at=self._clock(),
        )
        log_basr(
            self._structured_logger,
            "browser_recognition",
            "ingress_rejected_transport",
            trace=trace,
            payload={"reject_code": code},
        )

    async def _accept_payload(self, transport_id: int, payload: dict[str, Any]) -> tuple[bool, str | None]:
        async with self._lock:
            if transport_id != self._active_transport_id:
                self._snapshot["browser_stale_events_ignored"] = int(self._snapshot["browser_stale_events_ignored"]) + 1
                return False, "wrong_transport"
            session_id = str(payload.get("session_id", "") or "").strip() or None
            generation_id = int(payload.get("generation_id", 0) or 0)
            if session_id and self._active_client_session_id and session_id != self._active_client_session_id:
                self._active_client_session_id = session_id
                self._active_generation_id = generation_id
                return True, None
            if session_id and not self._active_client_session_id:
                self._active_client_session_id = session_id
            if generation_id and generation_id < self._active_generation_id:
                self._snapshot["browser_stale_events_ignored"] = int(self._snapshot["browser_stale_events_ignored"]) + 1
                return False, "stale_generation"
            if generation_id:
                self._active_generation_id = generation_id
            return True, None

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)
