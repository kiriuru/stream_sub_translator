from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import FastAPI, WebSocket


class BrowserAsrService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app
        self._lock = asyncio.Lock()
        self._active_transport_id = 0
        self._active_websocket: WebSocket | None = None
        self._active_client_session_id: str | None = None
        self._active_generation_id: int = 0
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
            "browser_stale_events_ignored": 0,
        }

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
                    "duplicate_partial_suppressed": 0,
                    "duplicate_final_suppressed": 0,
                    "late_forced_final_suppressed": 0,
                    "mic_track_ready_state": None,
                    "mic_track_muted": False,
                    "mic_rms": 0.0,
                    "mic_active_recent_ms": None,
                    "last_mic_activity_at": None,
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
                    "last_seen_at_ms": self._now_ms(),
                }
            )
        await self._runtime_orchestrator.browser_asr_worker_disconnected()

    async def worker_connected(self) -> None:
        await self._runtime_orchestrator.browser_asr_worker_connected()

    async def handle_status(self, transport_id: int, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        accepted = await self._accept_payload(transport_id, payload)
        if not accepted:
            return False
        snapshot_update = {
            "worker_connected": True,
            "recognition_state": str(payload.get("recognition_state", self._snapshot["recognition_state"]) or "idle"),
            "supervisor_state": str(payload.get("browser_supervisor_state", payload.get("supervisor_state", "idle")) or "idle"),
            "desired_running": bool(payload.get("desired_running", False)),
            "degraded_reason": payload.get("degraded_reason"),
            "last_error": payload.get("last_error"),
            "last_seen_at_ms": self._now_ms(),
            "generation_id": int(payload.get("generation_id", self._snapshot["generation_id"]) or 0),
            "session_id": str(payload.get("session_id", self._snapshot["session_id"]) or "").strip() or None,
            "client_segment_id": str(payload.get("client_segment_id", self._snapshot["client_segment_id"]) or "").strip() or None,
            "forced_final": bool(payload.get("forced_final", self._snapshot["forced_final"])),
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
        }
        async with self._lock:
            self._snapshot.update(snapshot_update)
        await self._runtime_orchestrator.update_browser_asr_worker_status(payload)
        return True

    async def handle_external_update(self, transport_id: int, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        accepted = await self._accept_payload(transport_id, payload)
        if not accepted:
            return False
        await self._runtime_orchestrator.ingest_external_asr_update(
            partial=str(payload.get("partial", "") or ""),
            final=str(payload.get("final", "") or ""),
            is_final=bool(payload.get("is_final", False)),
            source_lang=str(payload.get("source_lang", "") or "") or None,
            generation_id=int(payload.get("generation_id", 0) or 0),
            session_id=str(payload.get("session_id", "") or "").strip() or None,
            client_segment_id=str(payload.get("client_segment_id", "") or "").strip() or None,
            forced_final=bool(payload.get("forced_final", False)),
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

    async def _accept_payload(self, transport_id: int, payload: dict[str, Any]) -> bool:
        async with self._lock:
            if transport_id != self._active_transport_id:
                self._snapshot["browser_stale_events_ignored"] = int(self._snapshot["browser_stale_events_ignored"]) + 1
                return False
            session_id = str(payload.get("session_id", "") or "").strip() or None
            generation_id = int(payload.get("generation_id", 0) or 0)
            if session_id and self._active_client_session_id and session_id != self._active_client_session_id:
                self._active_client_session_id = session_id
                self._active_generation_id = generation_id
                return True
            if session_id and not self._active_client_session_id:
                self._active_client_session_id = session_id
            if generation_id and generation_id < self._active_generation_id:
                self._snapshot["browser_stale_events_ignored"] = int(self._snapshot["browser_stale_events_ignored"]) + 1
                return False
            if generation_id:
                self._active_generation_id = generation_id
            return True

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)
