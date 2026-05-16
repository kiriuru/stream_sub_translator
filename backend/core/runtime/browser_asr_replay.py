"""Opt-in JSONL recorder + operational replay (Domain A / controlled clock)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

from backend.core.runtime.browser_asr_operational_fsm import BrowserAsrOperationalFsm
from backend.core.runtime.browser_asr_recovery_policy import (
    BrowserAsrRecoveryPolicy,
    BrowserAsrPolicyExecutor,
)
from backend.core.runtime.browser_asr_trace import BrowserAsrTraceFields
from backend.core.timekeeping import SteppedMonotonicClock


class BrowserAsrJsonlRecorder:
    """Writes only operational rows (no L5 RMS spam). Enabled via SST_BROWSER_ASR_RECORD_JSONL path."""

    def __init__(self, path: Path | None) -> None:
        self._path = Path(path) if path else None

    @classmethod
    def from_env(cls) -> BrowserAsrJsonlRecorder:
        raw = str(os.environ.get("SST_BROWSER_ASR_RECORD_JSONL", "") or "").strip()
        if not raw:
            return cls(None)
        return cls(Path(raw))

    def maybe_record(self, row: dict[str, Any]) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            return


def _trace_from_row(row: dict[str, Any]) -> BrowserAsrTraceFields:
    return BrowserAsrTraceFields(
        event_id=str(row.get("event_id") or "replay"),
        causal_parent_id=row.get("causal_parent_id"),
        generation_id=int(row["generation_id"]) if row.get("generation_id") is not None else None,
        session_id=row.get("session_id"),
        transport_id=int(row["transport_id"]) if row.get("transport_id") is not None else None,
        mono_ingress_at=float(row["mono_ingress_at"]) if row.get("mono_ingress_at") is not None else None,
    )


def iter_jsonl_records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def replay_operational_jsonl(
    path: Path,
    *,
    clock: SteppedMonotonicClock | None = None,
) -> dict[str, Any]:
    """
    Deterministic **operational** outcome: FSM phase + policy counters (not bit-identical runtime).
    """
    clock = clock or SteppedMonotonicClock()
    fsm = BrowserAsrOperationalFsm(structured_logger=None)
    policy = BrowserAsrRecoveryPolicy()
    executor = BrowserAsrPolicyExecutor(structured_logger=None, can_send_control=lambda: False)
    ingress_rejects = 0
    for row in iter_jsonl_records(path):
        kind = str(row.get("kind") or "")
        clock.advance(float(row.get("advance_mono", 0) or 0))
        if kind == "worker_connected":
            fsm.note_worker_connected(trace=_trace_from_row(row))
        elif kind == "status":
            fsm.note_status_aggregate(
                recognition_state=row.get("recognition_state"),
                supervisor_state=row.get("supervisor_state"),
                degraded_reason=row.get("degraded_reason"),
                worker_connected=bool(row.get("worker_connected", True)),
                trace=_trace_from_row(row),
            )
        elif kind == "ingest":
            fsm.note_ingest(is_final=bool(row.get("is_final")), trace=_trace_from_row(row))
        elif kind == "ingress_reject":
            ingress_rejects += 1
        elif kind == "policy_cycle":
            actions = policy.suggest(
                degraded_reason=row.get("degraded_reason"),
                last_error=row.get("last_error"),
                worker_connected=bool(row.get("worker_connected", True)),
            )
            executor.execute(actions=actions, trace=_trace_from_row(row))
        elif kind == "worker_disconnected":
            fsm.note_worker_disconnected(trace=_trace_from_row(row))

    return {
        "fsm_phase": fsm.phase.value,
        "ingress_rejects": ingress_rejects,
    }


__all__ = [
    "BrowserAsrJsonlRecorder",
    "replay_operational_jsonl",
    "iter_jsonl_records",
]
