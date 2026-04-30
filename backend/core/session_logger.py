from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class SessionLogManager:
    _CHANNEL_FILES = {
        "dashboard": "dashboard-live-events.log",
        "overlay": "overlay-events.log",
        "browser_worker": "browser-recognition-live.log",
    }

    def __init__(self, logs_dir: Path) -> None:
        self._logs_dir = logs_dir
        self._lock = threading.Lock()
        self._last_line_by_channel: dict[str, str | None] = {}
        self._repeat_count_by_channel: dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._logs_dir.mkdir(parents=True, exist_ok=True)
            for channel in self._CHANNEL_FILES:
                self._log_path(channel).write_text("", encoding="utf-8")
                self._last_line_by_channel[channel] = None
                self._repeat_count_by_channel[channel] = 0

    def flush(self) -> None:
        with self._lock:
            for channel in self._CHANNEL_FILES:
                self._flush_repeats_locked(channel)

    def log(self, channel: str, message: str, *, source: str | None = None, details: dict | None = None) -> None:
        normalized_channel = self._normalize_channel(channel)
        normalized_message = " ".join(str(message or "").strip().split())
        if not normalized_message:
            return
        line = self._format_line(normalized_message, source=source, details=details)
        with self._lock:
            last_line = self._last_line_by_channel.get(normalized_channel)
            if last_line == line:
                self._repeat_count_by_channel[normalized_channel] = self._repeat_count_by_channel.get(normalized_channel, 1) + 1
                return
            self._flush_repeats_locked(normalized_channel)
            self._append_line_locked(normalized_channel, line)
            self._last_line_by_channel[normalized_channel] = line
            self._repeat_count_by_channel[normalized_channel] = 1

    def _normalize_channel(self, channel: str) -> str:
        normalized = str(channel or "").strip().lower()
        return normalized if normalized in self._CHANNEL_FILES else "dashboard"

    def _log_path(self, channel: str) -> Path:
        return self._logs_dir / self._CHANNEL_FILES[channel]

    def _append_line_locked(self, channel: str, line: str) -> None:
        with self._log_path(channel).open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    def _flush_repeats_locked(self, channel: str) -> None:
        repeat_count = self._repeat_count_by_channel.get(channel, 0)
        if repeat_count > 1:
            self._append_line_locked(channel, f"[repeat] previous line repeated {repeat_count - 1} more time(s)")
        self._last_line_by_channel[channel] = None
        self._repeat_count_by_channel[channel] = 0

    def _format_line(self, message: str, *, source: str | None = None, details: dict | None = None) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        parts = [f"[{timestamp}]"]
        if source:
            parts.append(f"[{str(source).strip().lower()}]")
        parts.append(message)
        if details:
            try:
                parts.append(json.dumps(details, ensure_ascii=False, sort_keys=True))
            except Exception:
                parts.append(str(details))
        return " ".join(part for part in parts if part)
