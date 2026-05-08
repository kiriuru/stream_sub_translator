from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(slots=True)
class RemoteAudioStateController:
    """
    Centralizes remote audio ingest session bookkeeping and queue lifecycle.
    """

    ensure_queue: Callable[[], Awaitable[None]]
    shutdown_queue: Callable[[], Awaitable[None]]
    clear_queue: Callable[[], Awaitable[None]]

    set_connected: Callable[[bool], None]
    set_session_id: Callable[[str | None], None]
    set_last_chunk_monotonic: Callable[[float | None], None]

    now_monotonic: Callable[[], float]

    async def init_for_start(self) -> None:
        await self.ensure_queue()
        await self.clear_queue()
        self.set_connected(False)
        self.set_session_id(None)
        self.set_last_chunk_monotonic(None)

    async def shutdown_for_stop(self) -> None:
        await self.shutdown_queue()
        self.set_connected(False)
        self.set_session_id(None)
        self.set_last_chunk_monotonic(None)

    def note_connected(self, *, session_id: str | None = None) -> None:
        self.set_connected(True)
        cleaned = str(session_id or "").strip() or None
        self.set_session_id(cleaned)
        self.set_last_chunk_monotonic(self.now_monotonic())

    def note_disconnected(self) -> None:
        self.set_connected(False)
        self.set_session_id(None)
        self.set_last_chunk_monotonic(None)

