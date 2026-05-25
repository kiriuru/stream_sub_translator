"""Desktop launcher dependency bootstrap trace (Web Speech vs CPU/GPU install paths)."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_LOG_NAME = "deps-install-trace.jsonl"
_instance: DepsInstallTraceLog | None = None
_lock = threading.Lock()


class DepsInstallTraceLog:
    def __init__(self, logs_dir: Path) -> None:
        self._logs_dir = Path(logs_dir)
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._sequence = 0
        self._monotonic_origin = time.perf_counter()

    @classmethod
    def configure(cls, logs_dir: Path) -> DepsInstallTraceLog:
        global _instance
        with _lock:
            if _instance is None:
                _instance = DepsInstallTraceLog(logs_dir)
                _instance.reset()
            return _instance

    @classmethod
    def get(cls) -> DepsInstallTraceLog | None:
        return _instance

    def reset(self) -> None:
        try:
            self._logs_dir.mkdir(parents=True, exist_ok=True)
            self.path().write_text("", encoding="utf-8")
        except OSError:
            return

    def path(self) -> Path:
        return self._logs_dir / _LOG_NAME

    def log(self, phase: str, event: str, **fields: Any) -> None:
        normalized_phase = str(phase or "").strip() or "unknown"
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
                "phase": normalized_phase,
                "event": normalized_event,
                "process_id": os.getpid(),
                "thread": {
                    "id": threading.get_ident(),
                    "name": threading.current_thread().name,
                },
            }
            if fields:
                record["fields"] = {str(key): value for key, value in fields.items() if value is not None}
            self._append_record(record)

    def _append_record(self, record: Mapping[str, Any]) -> None:
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
            with self.path().open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
        except OSError:
            return


def configure_deps_install_trace(logs_dir: Path) -> DepsInstallTraceLog:
    return DepsInstallTraceLog.configure(logs_dir)


def deps_trace(phase: str, event: str, **fields: Any) -> None:
    logger = DepsInstallTraceLog.get()
    if logger is None:
        return
    logger.log(phase, event, **fields)
