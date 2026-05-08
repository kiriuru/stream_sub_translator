from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.core.runtime.speech_source import SpeechSourceCapabilities


@dataclass(slots=True)
class _LocalParakeetHooks:
    start: Callable[[], Awaitable[None]]
    stop: Callable[[], Awaitable[None]]


class LocalParakeetSpeechSource:
    """
    Local Parakeet speech source.

    Stage 6/8 stepping stone: this class makes the local source explicit and symmetric with
    browser/remote sources, while reusing the existing hook-based audio/tasks lifecycle.
    """

    name = "LocalParakeetSpeechSource"

    def __init__(self, hooks: _LocalParakeetHooks) -> None:
        self._hooks = hooks

    def capabilities(self) -> SpeechSourceCapabilities:
        return SpeechSourceCapabilities(
            kind="local_parakeet",
            uses_backend_audio_capture=True,
            uses_browser_worker=False,
            uses_remote_audio_source=False,
            uses_remote_event_source=False,
        )

    async def start(self) -> None:
        await self._hooks.start()

    async def stop(self) -> None:
        await self._hooks.stop()

    async def browser_worker_connected(self) -> None:
        return None

    async def browser_worker_disconnected(self) -> None:
        return None

    async def update_browser_worker_status(self, payload: dict[str, Any]) -> None:
        _ = payload
        return None

    async def ingest_external_asr_update(self, **payload: Any) -> None:
        _ = payload
        return None

    async def ingest_remote_audio_chunk(self, payload: bytes) -> bool:
        _ = payload
        return False

    async def ingest_remote_transcript_event(self, payload: dict) -> bool:
        _ = payload
        return False

    async def ingest_remote_translation_event(self, payload: dict) -> bool:
        _ = payload
        return False


__all__ = ["LocalParakeetSpeechSource", "_LocalParakeetHooks"]

