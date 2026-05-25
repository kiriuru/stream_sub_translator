"""High-detail pipeline / thread / queue trace for local ASR triage (desktop installs).

Writes ``logs/pipeline-trace.jsonl`` — one JSON object per line with monotonic sequence,
OS thread identity, optional asyncio task name, and component-specific queue depths.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.core.redaction import redact_mapping

_LOG_NAME = "pipeline-trace.jsonl"
_instance: PipelineTraceLog | None = None
_lock = threading.Lock()


def _current_asyncio_task_name() -> str | None:
    try:
        task = asyncio.current_task()
    except RuntimeError:
        return None
    if task is None:
        return None
    name = getattr(task, "get_name", None)
    if callable(name):
        return str(name() or "") or None
    return None


def _running_loop_id() -> int | None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return id(loop)


class PipelineTraceLog:
    def __init__(self, logs_dir: Path) -> None:
        self._logs_dir = Path(logs_dir)
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._sequence = 0
        self._monotonic_origin = time.perf_counter()

    @classmethod
    def configure(cls, logs_dir: Path) -> PipelineTraceLog:
        global _instance
        with _lock:
            if _instance is None:
                _instance = PipelineTraceLog(logs_dir)
                _instance.reset()
            return _instance

    @classmethod
    def get(cls) -> PipelineTraceLog | None:
        return _instance

    def reset(self) -> None:
        try:
            self._logs_dir.mkdir(parents=True, exist_ok=True)
            self.path().write_text("", encoding="utf-8")
        except OSError:
            return

    def path(self) -> Path:
        return self._logs_dir / _LOG_NAME

    def log(
        self,
        lane: str,
        component: str,
        event: str,
        *,
        fields: Mapping[str, Any] | None = None,
    ) -> None:
        normalized_lane = str(lane or "").strip() or "unknown"
        normalized_component = str(component or "").strip() or "unknown"
        normalized_event = str(event or "").strip()
        if not normalized_event:
            return
        with _lock:
            self._sequence += 1
            record: dict[str, Any] = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "session_id": self._session_id,
                "sequence": self._sequence,
                "elapsed_ms": round((time.perf_counter() - self._monotonic_origin) * 1000.0, 2),
                "lane": normalized_lane,
                "component": normalized_component,
                "event": normalized_event,
                "process_id": os.getpid(),
                "thread": {
                    "id": threading.get_ident(),
                    "name": threading.current_thread().name,
                    "is_main": threading.current_thread() is threading.main_thread(),
                },
            }
            task_name = _current_asyncio_task_name()
            if task_name:
                record["asyncio_task"] = task_name
            loop_id = _running_loop_id()
            if loop_id is not None:
                record["asyncio_loop_id"] = loop_id
            if fields:
                record["fields"] = redact_mapping(
                    {str(key): value for key, value in fields.items() if value is not None}
                )
            self._append_record(record)

    def _append_record(self, record: Mapping[str, Any]) -> None:
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
            with self.path().open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
        except OSError:
            return


def configure_pipeline_trace_log(logs_dir: Path) -> PipelineTraceLog:
    return PipelineTraceLog.configure(logs_dir)


def pipeline_trace(
    lane: str,
    component: str,
    event: str,
    **fields: Any,
) -> None:
    logger = PipelineTraceLog.get()
    if logger is None:
        return
    logger.log(lane, component, event, fields=fields if fields else None)


def pipeline_trace_mapping(
    lane: str,
    component: str,
    event: str,
    payload: Mapping[str, Any] | None = None,
) -> None:
    if not payload:
        pipeline_trace(lane, component, event)
        return
    pipeline_trace(lane, component, event, **dict(payload))
