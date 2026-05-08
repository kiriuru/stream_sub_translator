from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.core.runtime.speech_source import SpeechSourceCapabilities
from backend.models import TranscriptEvent, TranslationEvent


@dataclass(slots=True)
class _RemoteControllerHooks:
    set_runtime_transcribing: Callable[[str], Awaitable[None]]
    set_runtime_translating: Callable[[str], Awaitable[None]]
    set_runtime_listening: Callable[[str], Awaitable[None]]
    transcript_sink: Callable[[TranscriptEvent], Awaitable[None]]
    handle_translation_event: Callable[[TranslationEvent], Awaitable[None]]
    increment_final_metric: Callable[[], None]


class RemoteControllerSpeechSource:
    """
    Remote controller mode: ingests transcript/translation events coming from a remote worker.

    Owns:
    - runtime phase messaging for remote streams
    - routing into TranscriptController + Subtitle/Translation handlers
    """

    name = "RemoteControllerSpeechSource"

    def __init__(self, hooks: _RemoteControllerHooks) -> None:
        self._hooks = hooks

    def capabilities(self) -> SpeechSourceCapabilities:
        return SpeechSourceCapabilities(
            kind="remote_controller",
            uses_backend_audio_capture=False,
            uses_browser_worker=False,
            uses_remote_audio_source=False,
            uses_remote_event_source=True,
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
        _ = payload
        return False

    async def ingest_remote_transcript_event(self, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        try:
            event = TranscriptEvent.model_validate(payload)
        except Exception:
            return False
        if event.event == "partial":
            await self._hooks.set_runtime_transcribing("Receiving remote worker transcript stream.")
        await self._hooks.transcript_sink(event)
        if event.event == "final":
            self._hooks.increment_final_metric()
            await self._hooks.set_runtime_listening("Remote worker transcript stream is active.")
        return True

    async def ingest_remote_translation_event(self, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        try:
            event = TranslationEvent.model_validate(payload)
        except Exception:
            return False
        await self._hooks.set_runtime_translating("Receiving remote worker translation stream.")
        await self._hooks.handle_translation_event(event)
        await self._hooks.set_runtime_listening("Remote worker transcript stream is active.")
        return True


__all__ = ["RemoteControllerSpeechSource", "_RemoteControllerHooks"]

