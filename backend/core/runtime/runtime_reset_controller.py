from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class RuntimeResetController:
    """
    Centralizes runtime reset sequences (stage 8 refinement).

    This is intentionally a thin wrapper over existing reset calls to keep behavior stable.
    """

    reset_vad: Callable[[], None]
    clear_segment_queue: Callable[[], None]
    reset_asr_runtime_state: Callable[[], None]
    reset_state_broadcast: Callable[[], None]
    clear_partial_tracking: Callable[[], None]
    reset_browser_worker_status_signature: Callable[[], None]

    def on_start_reset(self) -> None:
        self.reset_vad()
        self.reset_asr_runtime_state()
        self.clear_segment_queue()
        self.reset_state_broadcast()
        self.reset_browser_worker_status_signature()
        self.clear_partial_tracking()

    def on_stop_reset(self) -> None:
        # Stop path clears queues/state similarly; caller handles audio/source teardown separately.
        self.clear_segment_queue()
        self.reset_vad()
        self.reset_state_broadcast()
        self.reset_browser_worker_status_signature()
        self.clear_partial_tracking()

