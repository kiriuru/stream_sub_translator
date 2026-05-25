from __future__ import annotations

import time


class PipelineTraceSampler:
    """Rate-limit repetitive trace lines (e.g. per-callback) while keeping bursts visible."""

    def __init__(self, *, min_interval_ms: float = 250.0) -> None:
        self._interval_s = max(0.01, float(min_interval_ms) / 1000.0)
        self._last_by_key: dict[str, float] = {}

    def should_emit(self, key: str) -> bool:
        now = time.perf_counter()
        last = self._last_by_key.get(key, 0.0)
        if now - last < self._interval_s:
            return False
        self._last_by_key[key] = now
        return True
