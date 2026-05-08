from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class SegmentStateController:
    """
    Centralizes active segment bookkeeping and related cleanup hooks.
    """

    get_active_segment_id: Callable[[], str | None]
    clear_active_segment: Callable[[], None]
    clear_partial_tracking_for_segment: Callable[[str | None], None]

    def cleanup_on_browser_worker_disconnect(self) -> None:
        segment_id = self.get_active_segment_id()
        self.clear_active_segment()
        self.clear_partial_tracking_for_segment(segment_id)

