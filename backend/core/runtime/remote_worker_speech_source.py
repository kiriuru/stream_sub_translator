from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.core.runtime.speech_source import SpeechSourceCapabilities


@dataclass(slots=True)
class _RemoteWorkerHooks:
    ingest_remote_audio_chunk: Callable[[bytes], Awaitable[bool]]


class RemoteWorkerSpeechSource:
    """
    Remote worker mode: receives remote controller audio chunks and processes them via the existing
    remote audio queue + local ASR loops (those loops are started/stopped by generic SpeechSource hooks).
    """

    name = "RemoteWorkerSpeechSource"

    def __init__(self, hooks: _RemoteWorkerHooks) -> None:
        self._hooks = hooks

    def capabilities(self) -> SpeechSourceCapabilities:
        return SpeechSourceCapabilities(
            kind="remote_worker",
            uses_backend_audio_capture=False,
            uses_browser_worker=False,
            uses_remote_audio_source=True,
            uses_remote_event_source=False,
        )

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

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
        return bool(await self._hooks.ingest_remote_audio_chunk(payload))

    async def ingest_remote_transcript_event(self, payload: dict) -> bool:
        _ = payload
        return False

    async def ingest_remote_translation_event(self, payload: dict) -> bool:
        _ = payload
        return False


__all__ = ["RemoteWorkerSpeechSource", "_RemoteWorkerHooks"]

