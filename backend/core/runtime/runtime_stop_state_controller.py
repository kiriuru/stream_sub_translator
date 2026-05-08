from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class RuntimeStopStateController:
    """
    Centralizes the initial stop() bookkeeping that is purely state mutation.
    """

    clear_latest_status_message: Callable[[], None]
    bump_asr_runtime_generation: Callable[[], None]
    set_idle_state: Callable[[], None]

    def pre_stop(self) -> None:
        self.clear_latest_status_message()
        self.bump_asr_runtime_generation()
        self.set_idle_state()

