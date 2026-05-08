from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class SpeechSourceStateController:
    """
    Centralizes active speech source bookkeeping on the orchestrator facade.
    """

    get_active_source: Callable[[], Any | None]
    set_active_source: Callable[[Any | None], None]

    set_local_audio_device_id: Callable[[str | None], None]
    set_device_id: Callable[[str | None], None]

    choose_source: Callable[[bool, bool, bool], Any]
    browser_source: Any
    remote_controller_source: Any
    remote_worker_source: Any
    local_parakeet_source: Any

    def select_for_start(
        self,
        *,
        is_browser_mode: bool,
        uses_remote_audio_source: bool,
        uses_remote_event_source: bool,
    ) -> Any:
        _ = self.choose_source(is_browser_mode, uses_remote_audio_source, uses_remote_event_source)
        if is_browser_mode:
            source = self.browser_source
        elif uses_remote_event_source:
            source = self.remote_controller_source
        elif uses_remote_audio_source:
            source = self.remote_worker_source
        else:
            source = self.local_parakeet_source
        self.set_active_source(source)
        return source

    def clear_after_stop(self) -> None:
        self.set_active_source(None)
        self.set_local_audio_device_id(None)
        self.set_device_id(None)

