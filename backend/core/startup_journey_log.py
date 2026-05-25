"""Structured startup journey log (launch -> ASR listening) for desktop/local triage."""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.core.redaction import redact_mapping


class StartupJourneyLog:
    _LOG_NAME = "startup-journey.jsonl"
    _instance: StartupJourneyLog | None = None
    _lock = threading.Lock()

    def __init__(self, logs_dir: Path) -> None:
        self._logs_dir = Path(logs_dir)
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._sequence = 0

    @classmethod
    def configure(cls, logs_dir: Path) -> StartupJourneyLog:
        with cls._lock:
            if cls._instance is None:
                cls._instance = StartupJourneyLog(logs_dir)
                cls._instance.reset()
            return cls._instance

    @classmethod
    def get(cls) -> StartupJourneyLog | None:
        return cls._instance

    def reset(self) -> None:
        try:
            self._logs_dir.mkdir(parents=True, exist_ok=True)
            self.path().write_text("", encoding="utf-8")
        except OSError:
            return

    def path(self) -> Path:
        return self._logs_dir / self._LOG_NAME

    def log(self, phase: str, event: str, **fields: Any) -> None:
        normalized_phase = str(phase or "").strip() or "unknown"
        normalized_event = str(event or "").strip()
        if not normalized_event:
            return
        with self._lock:
            self._sequence += 1
            record: dict[str, Any] = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "session_id": self._session_id,
                "sequence": self._sequence,
                "phase": normalized_phase,
                "event": normalized_event,
            }
            if fields:
                record["fields"] = redact_mapping(
                    {str(key): value for key, value in fields.items() if value is not None}
                )
            self._append_record(record)

    def log_mapping(self, phase: str, event: str, payload: Mapping[str, Any] | None = None) -> None:
        if not payload:
            self.log(phase, event)
            return
        self.log(phase, event, **dict(payload))

    def _append_record(self, record: Mapping[str, Any]) -> None:
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
            with self.path().open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
        except OSError:
            return


def configure_startup_journey_log(logs_dir: Path) -> StartupJourneyLog:
    return StartupJourneyLog.configure(logs_dir)


def journey_log(phase: str, event: str, **fields: Any) -> None:
    logger = StartupJourneyLog.get()
    if logger is None:
        return
    logger.log(phase, event, **fields)


def journey_log_mapping(phase: str, event: str, payload: Mapping[str, Any] | None = None) -> None:
    logger = StartupJourneyLog.get()
    if logger is None:
        return
    logger.log_mapping(phase, event, payload)


def collect_runtime_environment_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "python_executable": os.environ.get("SST_PYTHON_EXECUTABLE") or sys.executable,
        "project_root": os.environ.get("SST_PROJECT_ROOT") or "",
        "bundle_root": os.environ.get("SST_BUNDLE_ROOT") or "",
        "desktop_launcher": os.environ.get("SST_DESKTOP_LAUNCHER") or "",
        "remote_role": os.environ.get("SST_REMOTE_ROLE") or "",
        "venv_handoff": os.environ.get("SST_VENV_LAUNCHER_REEXEC") or "",
    }
    try:
        import torch

        snapshot["torch_version"] = str(getattr(torch, "__version__", "") or "")
        snapshot["torch_cuda_is_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            snapshot["torch_cuda_device_name"] = str(torch.cuda.get_device_name(0))
    except Exception as exc:
        snapshot["torch_import_error"] = f"{type(exc).__name__}: {exc}"
    try:
        import sounddevice as sd

        snapshot["sounddevice_version"] = str(getattr(sd, "__version__", "") or "")
    except Exception as exc:
        snapshot["sounddevice_import_error"] = f"{type(exc).__name__}: {exc}"
    return snapshot
