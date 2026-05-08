from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class RuntimeStartStateController:
    """
    Centralizes start() state bookkeeping that is purely state mutation.
    """

    set_runtime_loop: Callable[[], None]
    clear_latest_status_message: Callable[[], None]
    reset_metrics: Callable[[], None]
    reset_in_flight_transcribe_count: Callable[[], None]

    def pre_start(self) -> None:
        self.set_runtime_loop()
        self.clear_latest_status_message()
        self.reset_metrics()
        self.reset_in_flight_transcribe_count()

