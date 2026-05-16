"""
L2 Operational FSM — narrow lifecycle derived from **normalized ingest events**
and **explicit status aggregates** (not raw diagnostics snapshots as authority).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from backend.core.runtime.browser_asr_trace import BrowserAsrTraceFields
from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.runtime.browser_asr_observability import BASR_EVENT_PREFIX
from backend.core.runtime.browser_asr_trace import log_basr, new_event_id


class BrowserOperationalPhase(str, Enum):
    IDLE = "idle"
    WORKER_SOCKET_IDLE = "worker_socket_idle"
    WORKER_LIVE = "worker_live"
    INGEST_PARTIAL = "ingest_partial"
    INGEST_FINAL = "ingest_final"
    DEGRADED_HINT = "degraded_hint"


class BrowserAsrOperationalFsm:
    def __init__(self, *, structured_logger: StructuredRuntimeLogger | None = None) -> None:
        self._structured_logger = structured_logger
        self._phase = BrowserOperationalPhase.IDLE
        self._last_status_aggregate: dict[str, Any] | None = None

    @property
    def phase(self) -> BrowserOperationalPhase:
        return self._phase

    def reset(self) -> None:
        self._phase = BrowserOperationalPhase.IDLE
        self._last_status_aggregate = None

    def note_worker_connected(self, *, trace: BrowserAsrTraceFields | None = None) -> None:
        self._transition(
            BrowserOperationalPhase.WORKER_SOCKET_IDLE,
            reason="worker_connected",
            trace=trace,
            log_always=True,
        )

    def note_worker_disconnected(self, *, trace: BrowserAsrTraceFields | None = None) -> None:
        self._transition(BrowserOperationalPhase.IDLE, reason="worker_disconnected", trace=trace, log_always=True)

    def note_status_aggregate(
        self,
        *,
        recognition_state: str | None,
        supervisor_state: str | None,
        degraded_reason: str | None,
        worker_connected: bool,
        trace: BrowserAsrTraceFields | None = None,
    ) -> None:
        agg = {
            "recognition_state": recognition_state,
            "supervisor_state": supervisor_state,
            "degraded_reason": degraded_reason,
            "worker_connected": worker_connected,
        }
        self._last_status_aggregate = agg
        if not worker_connected:
            return
        target = BrowserOperationalPhase.DEGRADED_HINT if degraded_reason else BrowserOperationalPhase.WORKER_LIVE
        self._transition(
            target,
            reason="status_aggregate",
            trace=trace,
            extra=agg,
            log_always=False,
        )

    def note_ingest(self, *, is_final: bool, trace: BrowserAsrTraceFields | None = None) -> None:
        target = BrowserOperationalPhase.INGEST_FINAL if is_final else BrowserOperationalPhase.INGEST_PARTIAL
        self._transition(target, reason="ingest", trace=trace, log_always=True)

    def _transition(
        self,
        new_phase: BrowserOperationalPhase,
        *,
        reason: str,
        trace: BrowserAsrTraceFields | None,
        extra: dict[str, Any] | None = None,
        log_always: bool = False,
    ) -> None:
        old = self._phase
        if new_phase == old and not log_always:
            return
        self._phase = new_phase
        tid = new_event_id()
        causal = trace.event_id if trace else None
        log_trace = BrowserAsrTraceFields(
            event_id=tid,
            causal_parent_id=causal,
            generation_id=trace.generation_id if trace else None,
            session_id=trace.session_id if trace else None,
            transport_id=trace.transport_id if trace else None,
            mono_ingress_at=trace.mono_ingress_at if trace else None,
        )
        payload: dict[str, Any] = {
            "from_phase": old.value,
            "to_phase": new_phase.value,
            "reason": reason,
        }
        if extra:
            payload.update(extra)
        log_basr(
            self._structured_logger,
            "browser_recognition",
            f"{BASR_EVENT_PREFIX}fsm_transition",
            trace=log_trace,
            payload=payload,
            source="browser_asr_operational_fsm",
        )
