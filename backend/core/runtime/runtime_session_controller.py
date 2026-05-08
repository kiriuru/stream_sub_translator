from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class RuntimeSessionController:
    """
    Centralizes runtime session bookkeeping (IDs/timestamps/sequence/generation/counters).

    Behavior is preserved: this controller only groups existing state transitions.
    """

    bump_asr_runtime_generation: Callable[[], None]
    set_sequence_zero: Callable[[], None]

    new_session_id: Callable[[], str]
    now_utc_iso: Callable[[], str]
    now_monotonic: Callable[[], float]

    set_session_started: Callable[[str, str, float], None]

    reset_export_session: Callable[[], None]
    reset_metrics: Callable[[], None]
    reset_in_flight_transcribe_count: Callable[[], None]
    clear_runtime_loop: Callable[[], None]

    def start_new_session(self) -> str:
        # Mirrors previous start() side effects ordering.
        self.reset_export_session()
        self.set_sequence_zero()
        self.bump_asr_runtime_generation()
        started_at = self.now_utc_iso()
        session_id = self.new_session_id()
        started_at_monotonic = self.now_monotonic()
        self.set_session_started(session_id, started_at, started_at_monotonic)
        return started_at

    def stop_cleanup(self) -> None:
        self.reset_export_session()
        self.reset_metrics()
        self.reset_in_flight_transcribe_count()
        self.clear_runtime_loop()

