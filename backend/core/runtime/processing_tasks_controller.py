from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(slots=True)
class ProcessingTasksController:
    """
    Owns the lifecycle of capture/ASR asyncio tasks.
    """

    get_capture_task: Callable[[], object | None]
    set_capture_task: Callable[[object | None], None]
    get_asr_task: Callable[[], object | None]
    set_asr_task: Callable[[object | None], None]

    create_capture_task: Callable[[], object]
    create_asr_task: Callable[[], object]

    await_task: Callable[[object], Awaitable[None]]

    def ensure_started(self) -> None:
        capture = self.get_capture_task()
        if capture is None or bool(getattr(capture, "done", lambda: False)()):
            self.set_capture_task(self.create_capture_task())

        asr = self.get_asr_task()
        if asr is None or bool(getattr(asr, "done", lambda: False)()):
            self.set_asr_task(self.create_asr_task())

    async def stop(self) -> None:
        tasks = [task for task in (self.get_capture_task(), self.get_asr_task()) if task is not None]
        for task in tasks:
            cancel = getattr(task, "cancel", None)
            if callable(cancel):
                cancel()
        for task in tasks:
            try:
                await self.await_task(task)
            except asyncio.CancelledError:
                pass
        self.set_capture_task(None)
        self.set_asr_task(None)

    def clear_refs(self) -> None:
        self.set_capture_task(None)
        self.set_asr_task(None)

