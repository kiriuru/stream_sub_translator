"""Structured dashboard/UI visibility trace for desktop/local triage."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.core.redaction import redact_mapping


class UiTraceLog:
    _LOG_NAME = "ui-trace.jsonl"
    _instance: UiTraceLog | None = None
    _lock = threading.Lock()

    def __init__(self, logs_dir: Path) -> None:
        self._logs_dir = Path(logs_dir)
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._sequence = 0

    @classmethod
    def configure(cls, logs_dir: Path) -> UiTraceLog:
        with cls._lock:
            if cls._instance is None:
                cls._instance = UiTraceLog(logs_dir)
                cls._instance.reset()
            return cls._instance

    @classmethod
    def get(cls) -> UiTraceLog | None:
        return cls._instance

    def reset(self) -> None:
        try:
            self._logs_dir.mkdir(parents=True, exist_ok=True)
            self.path().write_text("", encoding="utf-8")
        except OSError:
            return

    def path(self) -> Path:
        return self._logs_dir / self._LOG_NAME

    def log(self, surface: str, phase: str, event: str, **fields: Any) -> None:
        normalized_surface = str(surface or "").strip() or "dashboard"
        normalized_phase = str(phase or "").strip() or "ui"
        normalized_event = str(event or "").strip()
        if not normalized_event:
            return
        with self._lock:
            self._sequence += 1
            record: dict[str, Any] = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "session_id": self._session_id,
                "sequence": self._sequence,
                "surface": normalized_surface,
                "phase": normalized_phase,
                "event": normalized_event,
            }
            if fields:
                record["fields"] = redact_mapping(
                    {str(key): value for key, value in fields.items() if value is not None}
                )
            self._append_record(record)

    def log_mapping(
        self,
        surface: str,
        phase: str,
        event: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        if not payload:
            self.log(surface, phase, event)
            return
        self.log(surface, phase, event, **dict(payload))

    def _append_record(self, record: Mapping[str, Any]) -> None:
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
            with self.path().open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
        except OSError:
            return


def configure_ui_trace_log(logs_dir: Path) -> UiTraceLog:
    return UiTraceLog.configure(logs_dir)


def ui_trace(surface: str, phase: str, event: str, **fields: Any) -> None:
    logger = UiTraceLog.get()
    if logger is None:
        return
    logger.log(surface, phase, event, **fields)


def ui_trace_mapping(
    surface: str,
    phase: str,
    event: str,
    payload: Mapping[str, Any] | None = None,
) -> None:
    logger = UiTraceLog.get()
    if logger is None:
        return
    logger.log_mapping(surface, phase, event, payload)
