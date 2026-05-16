"""Domain A trace helpers for browser ASR (event_id / causal_parent / correlation)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from backend.core.runtime.browser_asr_observability import BASR_EVENT_PREFIX
from backend.core.structured_runtime_logger import StructuredRuntimeLogger


def new_event_id() -> str:
    return str(uuid.uuid4())


def basr_event(name: str) -> str:
    n = str(name or "").strip().lower()
    if n.startswith(BASR_EVENT_PREFIX):
        return n
    return f"{BASR_EVENT_PREFIX}{n.lstrip('.')}"


@dataclass(slots=True)
class BrowserAsrTraceFields:
    event_id: str
    causal_parent_id: str | None
    generation_id: int | None
    session_id: str | None
    transport_id: int | None
    mono_ingress_at: float | None = None

    def as_log_payload(self) -> dict[str, Any]:
        return {
            "basr_event_id": self.event_id,
            "basr_causal_parent_id": self.causal_parent_id,
            "generation_id": self.generation_id,
            "session_id": self.session_id,
            "transport_id": self.transport_id,
            "mono_ingress_at": self.mono_ingress_at,
        }


def merge_trace_payload(base: Mapping[str, Any] | None, trace: BrowserAsrTraceFields | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if base:
        out.update(dict(base))
    if trace:
        out.update({k: v for k, v in trace.as_log_payload().items() if v is not None})
    return out


def log_basr(
    logger: StructuredRuntimeLogger | None,
    channel: str,
    event: str,
    *,
    trace: BrowserAsrTraceFields | None = None,
    payload: Mapping[str, Any] | None = None,
    source: str = "browser_asr_trace",
    **fields: Any,
) -> None:
    if logger is None:
        return
    merged = merge_trace_payload(payload, trace)
    logger.log(channel, basr_event(event), source=source, payload=merged or None, **fields)


__all__ = [
    "BrowserAsrTraceFields",
    "basr_event",
    "log_basr",
    "merge_trace_payload",
    "new_event_id",
]
