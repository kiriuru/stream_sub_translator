from __future__ import annotations

import queue
import time
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
        self._queue: queue.Queue[AsrWorkItem] = queue.Queue()

    def push(self, item: AsrWorkItem) -> None:
        if item.created_at_monotonic <= 0:
            item.created_at_monotonic = time.perf_counter()
        self._queue.put(item)

    def pop(self, timeout: float = 0.25) -> AsrWorkItem | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
