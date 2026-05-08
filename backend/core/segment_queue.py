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
    generation: int = 0
    segment_id: str = ""
    revision: int = 0
    vad_ms: float = 0.0
    created_at_monotonic: float = 0.0
    audio_segment_started_at_ms: int | None = None
    vad_partial_ready_at_ms: int | None = None
    asr_job_enqueued_at_ms: int | None = None


class SegmentQueue:
    def __init__(self, *, maxsize: int = 64) -> None:
        self._items: deque[AsrWorkItem] = deque()
        self._condition = threading.Condition()
        self._maxsize = max(1, int(maxsize or 1))
        self._partial_jobs_dropped = 0
        self._partial_jobs_coalesced = 0
        self._finals_prioritized_count = 0
        self._wake_counter = 0

    def _prune_redundant_partials_locked(self, item: AsrWorkItem) -> None:
        if not self._items:
            return

        retained: deque[AsrWorkItem] = deque()
        removed_count = 0
        for existing in self._items:
            if (
                existing.segment_id
                and existing.segment_id == item.segment_id
                and existing.kind == "partial"
            ):
                removed_count += 1
                continue
            retained.append(existing)
        self._items = retained
        if removed_count:
            self._partial_jobs_coalesced += removed_count

    def _drop_oldest_partial_locked(self) -> bool:
        retained: deque[AsrWorkItem] = deque()
        removed = False
        while self._items:
            existing = self._items.popleft()
            if not removed and existing.kind == "partial":
                removed = True
                self._partial_jobs_dropped += 1
                continue
            retained.append(existing)
        self._items = retained
        return removed

    def _pop_next_locked(self) -> AsrWorkItem | None:
        if not self._items:
            return None
        # Finals should not get stuck behind long partial backlogs.
        for item in self._items:
            if item.kind == "final":
                try:
                    self._items.remove(item)
                except ValueError:
                    break
                self._finals_prioritized_count += 1
                return item
        return self._items.popleft()

    def push(self, item: AsrWorkItem) -> None:
        if item.created_at_monotonic <= 0:
            item.created_at_monotonic = time.perf_counter()
        with self._condition:
            if item.kind == "partial" and item.segment_id:
                self._prune_redundant_partials_locked(item)
            elif item.kind == "final" and item.segment_id:
                self._prune_redundant_partials_locked(item)
            if len(self._items) >= self._maxsize:
                dropped_existing_partial = self._drop_oldest_partial_locked()
                if not dropped_existing_partial:
                    if item.kind == "partial":
                        self._partial_jobs_dropped += 1
                        self._condition.notify_all()
                        return
                    self._items.popleft()
            self._items.append(item)
            self._condition.notify()

    def pop(self, timeout: float = 0.25) -> AsrWorkItem | None:
        deadline = time.perf_counter() + max(0.0, timeout)
        with self._condition:
            wake_counter = self._wake_counter
            while not self._items:
                if wake_counter != self._wake_counter:
                    return None
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=remaining)
            return self._pop_next_locked()

    def clear(self, *, notify: bool = True) -> None:
        with self._condition:
            self._items.clear()
            if notify:
                self._wake_counter += 1
                self._condition.notify_all()

    def wake(self) -> None:
        with self._condition:
            self._wake_counter += 1
            self._condition.notify_all()

    def qsize(self) -> int:
        with self._condition:
            return len(self._items)

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def partial_jobs_dropped(self) -> int:
        with self._condition:
            return self._partial_jobs_dropped

    @property
    def partial_jobs_coalesced(self) -> int:
        with self._condition:
            return self._partial_jobs_coalesced

    @property
    def finals_prioritized_count(self) -> int:
        with self._condition:
            return self._finals_prioritized_count
