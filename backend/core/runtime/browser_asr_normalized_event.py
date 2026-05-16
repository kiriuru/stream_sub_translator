"""L1 normalized browser ASR message (after WebSocket JSON accept)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.runtime.browser_asr_trace import BrowserAsrTraceFields


@dataclass(slots=True)
class NormalizedBrowserAsrIngest:
    partial: str
    final: str
    is_final: bool
    source_lang: str | None
    generation_id: int
    session_id: str | None
    client_segment_id: str | None
    forced_final: bool
    asr_result_created_at_ms: int | None
    worker_send_started_at_ms: int | None
    worker_message_sequence: int | None
    backend_received_at_ms: int | None
    trace: BrowserAsrTraceFields
    raw_kind: str = "asr_update"


__all__ = ["NormalizedBrowserAsrIngest"]

