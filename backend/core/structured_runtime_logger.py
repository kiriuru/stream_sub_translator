from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.core.compact_log_line import format_structured_runtime_line, structured_event_level
from backend.core.diagnostic_flags import is_runtime_events_verbose_enabled
from backend.core.redaction import redact_mapping
from backend.core.structured_log_compact import compact_mapping_for_runtime_log

# Severity levels that always reach disk. DBG/VRB events (~95% of runtime
# noise on a real session — browser ASR FSM transitions, browser worker
# status heartbeats, translation queue depth ticks) are filtered unless
# SST_DEEP_DIAGNOSTICS / SST_TRACE_RUNTIME_EVENTS_VERBOSE is set.
_RUNTIME_EVENT_DEFAULT_LEVELS: frozenset[str] = frozenset({"INF", "WRN", "ERR", "CRT"})


class StructuredRuntimeLogger:
    _LOG_FILE = "runtime-events.log"

    def __init__(
        self,
        logs_dir: Path,
        *,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 2,
    ) -> None:
        self._logs_dir = Path(logs_dir)
        self._max_bytes = max(1_048_576, int(max_bytes))
        self._backup_count = max(1, int(backup_count))
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        """
        Truncate the current runtime events log on app startup.

        The export service already treats `runtime-events.log` as "latest" diagnostics; keeping old
        runs in the same file makes session exports noisy and can confuse postmortem inspection.
        Rotation is still used within a single run to cap disk usage.
        """
        try:
            with self._lock:
                self._logs_dir.mkdir(parents=True, exist_ok=True)
                log_path = self._log_path()
                log_path.write_text("", encoding="utf-8")
                for index in range(1, self._backup_count + 1):
                    rotated_path = log_path.with_suffix(f"{log_path.suffix}.{index}")
                    if rotated_path.exists():
                        rotated_path.unlink()
        except Exception:
            return

    def log(
        self,
        channel: str,
        event: str,
        *,
        source: str | None = None,
        payload: Mapping[str, Any] | None = None,
        **fields: Any,
    ) -> None:
        normalized_event = str(event or "").strip()
        if not normalized_event:
            return
        # Drop high-frequency DBG/VRB lines unless the user opted into verbose
        # runtime events. Matches the 0.4.1 footprint on user installs while
        # still allowing full triage via SST_DEEP_DIAGNOSTICS.
        if (
            structured_event_level(normalized_event) not in _RUNTIME_EVENT_DEFAULT_LEVELS
            and not is_runtime_events_verbose_enabled()
        ):
            return
        record: dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "channel": str(channel or "").strip().lower() or "runtime_metrics",
            "event": normalized_event,
        }
        normalized_source = str(source or "").strip()
        if normalized_source:
            record["source"] = normalized_source
        if payload:
            record.update(compact_mapping_for_runtime_log(self.redact_mapping(payload)))
        if fields:
            record.update(compact_mapping_for_runtime_log(self.redact_mapping(fields)))
        self._write_record(record)

    def redact_mapping(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return redact_mapping(payload)

    def _log_path(self) -> Path:
        return self._logs_dir / self._LOG_FILE

    def _write_record(self, record: Mapping[str, Any]) -> None:
        try:
            line = format_structured_runtime_line(record)
        except Exception:
            return
        try:
            with self._lock:
                self._logs_dir.mkdir(parents=True, exist_ok=True)
                log_path = self._log_path()
                self._rotate_if_needed_locked(log_path)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{line}\n")
        except Exception:
            return

    def _rotate_if_needed_locked(self, log_path: Path) -> None:
        try:
            if not log_path.exists():
                return
            if log_path.stat().st_size < self._max_bytes:
                return
            for index in range(self._backup_count, 0, -1):
                rotated_path = log_path.with_suffix(f"{log_path.suffix}.{index}")
                if not rotated_path.exists():
                    continue
                if index >= self._backup_count:
                    rotated_path.unlink()
                else:
                    rotated_path.replace(log_path.with_suffix(f"{log_path.suffix}.{index + 1}"))
            log_path.replace(log_path.with_suffix(f"{log_path.suffix}.1"))
        except Exception:
            return
