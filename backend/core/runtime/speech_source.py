from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class SpeechSourceCapabilities:
    kind: str
    uses_backend_audio_capture: bool
    uses_browser_worker: bool
    uses_remote_audio_source: bool
    uses_remote_event_source: bool


class SpeechSource(Protocol):
    name: str

    def capabilities(self) -> SpeechSourceCapabilities: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def browser_worker_connected(self) -> None: ...

    async def browser_worker_disconnected(self) -> None: ...

    async def update_browser_worker_status(self, payload: dict[str, Any]) -> None: ...

    async def ingest_external_asr_update(self, **payload: Any) -> None: ...

    async def ingest_remote_audio_chunk(self, payload: bytes) -> bool: ...

    async def ingest_remote_transcript_event(self, payload: dict) -> bool: ...

    async def ingest_remote_translation_event(self, payload: dict) -> bool: ...

