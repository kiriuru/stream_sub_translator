from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class BrowserWorkerStateController:
    """
    Centralizes browser speech worker connection/session bookkeeping.
    """

    set_external_worker_connected: Callable[[bool], None]
    set_active_session_id: Callable[[str | None], None]
    set_active_generation_id: Callable[[int], None]
    clear_status_signature: Callable[[], None]
    set_status_signature: Callable[[object], None]

    def reset_for_start(self) -> None:
        self.set_external_worker_connected(False)
        self.set_active_session_id(None)
        self.set_active_generation_id(0)
        self.clear_status_signature()

    def reset_for_stop(self) -> None:
        self.reset_for_start()

    def update_status_signature(self, signature: object) -> None:
        self.set_status_signature(signature)

