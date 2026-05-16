"""
Monotonic clocks for interval logic (ASR/browser path, TTL, policy cooldown).

Wall clock (`time.time`) must not be used for comparing \"how much time passed\"
in these paths; use MonotonicClock (`perf_counter`-based by default).
"""

from __future__ import annotations

import time
from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class MonotonicClock(Protocol):
    def __call__(self) -> float:
        """Return monotonic seconds (e.g. perf_counter)."""


def perf_counter_clock() -> float:
    return time.perf_counter()


class SteppedMonotonicClock:
    """Deterministic clock for replay/tests: advance via `set_time` / `advance`."""

    def __init__(self, *, start: float = 0.0) -> None:
        self._t = float(start)

    def __call__(self) -> float:
        return float(self._t)

    def set_time(self, value: float) -> None:
        self._t = float(value)

    def advance(self, delta_seconds: float) -> None:
        self._t += float(delta_seconds)


def as_callable(clock: MonotonicClock | Callable[[], float]) -> Callable[[], float]:
    return clock  # type: ignore[return-value]


__all__ = [
    "MonotonicClock",
    "perf_counter_clock",
    "SteppedMonotonicClock",
    "as_callable",
]
