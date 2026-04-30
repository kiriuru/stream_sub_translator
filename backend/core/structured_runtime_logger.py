from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class StructuredRuntimeLogger:
    _DEFAULT_CHANNEL_FILES = {
        "translation_dispatcher": "translation-dispatcher.log",
        "browser_recognition": "browser-recognition.log",
        "runtime_metrics": "runtime-metrics.log",
    }
    _REDACTED = "[redacted]"
    _SENSITIVE_KEYS = {
        "api_key",
        "access_token",
        "refresh_token",
        "client_secret",
        "password",
        "token",
        "authorization",
        "secret",
        "bearer",
        "credential",
        "credentials",
        "pair_code",
    }
    _SENSITIVE_KEY_SUBSTRINGS = (
        "api_key",
        "token",
        "secret",
        "password",
        "authorization",
        "bearer",
        "credential",
        "pair_code",
    )

    def __init__(
        self,
        logs_dir: Path,
        *,
        channel_files: Mapping[str, str] | None = None,
        max_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self._logs_dir = Path(logs_dir)
        self._channel_files = dict(channel_files or self._DEFAULT_CHANNEL_FILES)
        self._max_bytes = max(1_048_576, int(max_bytes))
        self._lock = threading.Lock()

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
        record: dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": normalized_event,
        }
        normalized_source = str(source or "").strip()
        if normalized_source:
            record["source"] = normalized_source
        if payload:
            record.update(self.redact_mapping(payload))
        if fields:
            record.update(self.redact_mapping(fields))
        self._write_record(channel, record)

    def redact_mapping(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            sanitized[str(key)] = self._redact_value(str(key), value)
        return sanitized

    def _redact_value(self, key: str | None, value: Any) -> Any:
        normalized_key = str(key or "").strip().lower()
        if self._is_sensitive_key(normalized_key):
            return self._REDACTED
        if isinstance(value, Mapping):
            return {str(child_key): self._redact_value(str(child_key), child_value) for child_key, child_value in value.items()}
        if isinstance(value, list):
            return [self._redact_value(None, item) for item in value]
        if isinstance(value, tuple):
            return [self._redact_value(None, item) for item in value]
        return value

    def _is_sensitive_key(self, normalized_key: str) -> bool:
        if not normalized_key:
            return False
        if normalized_key in self._SENSITIVE_KEYS:
            return True
        return any(fragment in normalized_key for fragment in self._SENSITIVE_KEY_SUBSTRINGS)

    def _normalize_channel(self, channel: str) -> str:
        normalized = str(channel or "").strip().lower()
        return normalized if normalized in self._channel_files else "runtime_metrics"

    def _log_path(self, channel: str) -> Path:
        return self._logs_dir / self._channel_files[channel]

    def _write_record(self, channel: str, record: Mapping[str, Any]) -> None:
        normalized_channel = self._normalize_channel(channel)
        try:
            line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        except Exception:
            return
        try:
            with self._lock:
                self._logs_dir.mkdir(parents=True, exist_ok=True)
                log_path = self._log_path(normalized_channel)
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
            rotated_path = log_path.with_suffix(f"{log_path.suffix}.1")
            if rotated_path.exists():
                rotated_path.unlink()
            log_path.replace(rotated_path)
        except Exception:
            return
