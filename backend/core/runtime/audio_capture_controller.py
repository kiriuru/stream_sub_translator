from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class AudioCaptureController:
    """
    Owns AudioCapture start/stop and the stored instance.
    """

    get_capture: Callable[[], Any | None]
    set_capture: Callable[[Any | None], None]
    create_capture: Callable[[], Any]
    get_device_id: Callable[[], str | None]
    stop_in_thread: Callable[[Any], Awaitable[None]]

    def start_if_needed(self) -> None:
        if self.get_capture() is not None:
            return
        device_id = self.get_device_id()
        if device_id is None:
            return
        capture = self.create_capture()
        capture.start(device_id=device_id)
        self.set_capture(capture)

    async def stop_if_running(self) -> None:
        capture = self.get_capture()
        if capture is None:
            return
        await self.stop_in_thread(capture)
        self.set_capture(None)

