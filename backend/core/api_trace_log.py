"""Structured HTTP / WebSocket API trace for local desktop triage."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.core.redaction import redact_mapping


class ApiTraceLog:
    _LOG_NAME = "api-trace.jsonl"
    _instance: ApiTraceLog | None = None
    _lock = threading.Lock()

    def __init__(self, logs_dir: Path) -> None:
        self._logs_dir = Path(logs_dir)
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._sequence = 0
        self._monotonic_origin = time.perf_counter()

    @classmethod
    def configure(cls, logs_dir: Path) -> ApiTraceLog:
        with cls._lock:
            if cls._instance is None:
                cls._instance = ApiTraceLog(logs_dir)
                cls._instance.reset()
            return cls._instance

    @classmethod
    def get(cls) -> ApiTraceLog | None:
        return cls._instance

    def reset(self) -> None:
        try:
            self._logs_dir.mkdir(parents=True, exist_ok=True)
            self.path().write_text("", encoding="utf-8")
        except OSError:
            return

    def path(self) -> Path:
        return self._logs_dir / self._LOG_NAME

    def log(self, channel: str, event: str, **fields: Any) -> None:
        normalized_channel = str(channel or "").strip() or "http"
        normalized_event = str(event or "").strip()
        if not normalized_event:
            return
        with self._lock:
            self._sequence += 1
            record: dict[str, Any] = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "session_id": self._session_id,
                "sequence": self._sequence,
                "elapsed_ms": round((time.perf_counter() - self._monotonic_origin) * 1000.0, 2),
                "channel": normalized_channel,
                "event": normalized_event,
            }
            if fields:
                record["fields"] = redact_mapping(
                    {str(key): value for key, value in fields.items() if value is not None}
                )
            self._append_record(record)

    def log_mapping(self, channel: str, event: str, payload: Mapping[str, Any] | None = None) -> None:
        if not payload:
            self.log(channel, event)
            return
        self.log(channel, event, **dict(payload))

    def _append_record(self, record: Mapping[str, Any]) -> None:
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
            with self.path().open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
        except OSError:
            return


def configure_api_trace_log(logs_dir: Path) -> ApiTraceLog:
    return ApiTraceLog.configure(logs_dir)


def api_trace(channel: str, event: str, **fields: Any) -> None:
    logger = ApiTraceLog.get()
    if logger is None:
        return
    logger.log(channel, event, **fields)
