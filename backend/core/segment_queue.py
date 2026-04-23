from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal


@dataclass
class AsrWorkItem:
    kind: Literal["partial", "final"]
    audio: bytes
    duration_ms: int
    segment_id: str = ""
    revision: int = 0
    vad_ms: float = 0.0
    created_at_monotonic: float = 0.0


class SegmentQueue:
    def __init__(self) -> None:
        self._items: deque[AsrWorkItem] = deque()
        self._condition = threading.Condition()

    def _prune_redundant_partials_locked(self, item: AsrWorkItem) -> None:
        if not self._items:
            return

        retained: deque[AsrWorkItem] = deque()
        for existing in self._items:
            if (
                existing.segment_id
                and existing.segment_id == item.segment_id
                and existing.kind == "partial"
            ):
                continue
            retained.append(existing)
        self._items = retained

    def push(self, item: AsrWorkItem) -> None:
        if item.created_at_monotonic <= 0:
            item.created_at_monotonic = time.perf_counter()
        with self._condition:
            if item.kind == "partial" and item.segment_id:
                self._prune_redundant_partials_locked(item)
            elif item.kind == "final" and item.segment_id:
                self._prune_redundant_partials_locked(item)
            self._items.append(item)
            self._condition.notify()

    def pop(self, timeout: float = 0.25) -> AsrWorkItem | None:
        deadline = time.perf_counter() + max(0.0, timeout)
        with self._condition:
            while not self._items:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=remaining)
            return self._items.popleft()

    def clear(self) -> None:
        with self._condition:
            self._items.clear()
