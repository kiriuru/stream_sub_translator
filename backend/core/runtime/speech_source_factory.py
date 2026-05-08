from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.core.runtime.speech_source import SpeechSource, SpeechSourceCapabilities


@dataclass(slots=True)
class _Hooks:
    browser_worker_connected: Callable[[], Awaitable[None]]
    browser_worker_disconnected: Callable[[], Awaitable[None]]
    update_browser_worker_status: Callable[[dict[str, Any]], Awaitable[None]]
    ingest_external_asr_update: Callable[..., Awaitable[None]]
    ingest_remote_audio_chunk: Callable[[bytes], Awaitable[bool]]
    ingest_remote_transcript_event: Callable[[dict], Awaitable[bool]]
    ingest_remote_translation_event: Callable[[dict], Awaitable[bool]]
    start_processing_tasks: Callable[[], Awaitable[None]]
    stop_processing_tasks: Callable[[], Awaitable[None]]
    start_audio_capture: Callable[[], Awaitable[None]]
    stop_audio_capture: Callable[[], Awaitable[None]]
    init_remote_audio: Callable[[], Awaitable[None]]
    shutdown_remote_audio: Callable[[], Awaitable[None]]
    init_browser_worker: Callable[[], Awaitable[None]]
    shutdown_browser_worker: Callable[[], Awaitable[None]]


class _BaseSource:
    def __init__(self, hooks: _Hooks, caps: SpeechSourceCapabilities, *, name: str) -> None:
        self._hooks = hooks
        self._caps = caps
        self.name = name

    def capabilities(self) -> SpeechSourceCapabilities:
        return self._caps

    async def start(self) -> None:
        if self._caps.uses_backend_audio_capture:
            await self._hooks.start_audio_capture()
        if self._caps.uses_browser_worker:
            await self._hooks.init_browser_worker()
        if self._caps.uses_remote_audio_source:
            await self._hooks.init_remote_audio()
        if self._caps.uses_backend_audio_capture or self._caps.uses_remote_audio_source:
            await self._hooks.start_processing_tasks()

    async def stop(self) -> None:
        await self._hooks.stop_processing_tasks()
        if self._caps.uses_remote_audio_source:
            await self._hooks.shutdown_remote_audio()
        if self._caps.uses_browser_worker:
            await self._hooks.shutdown_browser_worker()
        if self._caps.uses_backend_audio_capture:
            await self._hooks.stop_audio_capture()

    async def browser_worker_connected(self) -> None:
        if not self._caps.uses_browser_worker:
            return
        await self._hooks.browser_worker_connected()

    async def browser_worker_disconnected(self) -> None:
        if not self._caps.uses_browser_worker:
            return
        await self._hooks.browser_worker_disconnected()

    async def update_browser_worker_status(self, payload: dict[str, Any]) -> None:
        if not self._caps.uses_browser_worker:
            return
        await self._hooks.update_browser_worker_status(payload)

    async def ingest_external_asr_update(self, **payload: Any) -> None:
        if not self._caps.uses_browser_worker:
            return
        await self._hooks.ingest_external_asr_update(**payload)

    async def ingest_remote_audio_chunk(self, payload: bytes) -> bool:
        if not self._caps.uses_remote_audio_source:
            return False
        return bool(await self._hooks.ingest_remote_audio_chunk(payload))

    async def ingest_remote_transcript_event(self, payload: dict) -> bool:
        if not self._caps.uses_remote_event_source:
            return False
        return bool(await self._hooks.ingest_remote_transcript_event(payload))

    async def ingest_remote_translation_event(self, payload: dict) -> bool:
        if not self._caps.uses_remote_event_source:
            return False
        return bool(await self._hooks.ingest_remote_translation_event(payload))


class SpeechSourceFactory:
    def __init__(self, hooks: _Hooks) -> None:
        self._hooks = hooks

    def build(
        self,
        *,
        is_browser_mode: bool,
        uses_remote_audio_source: bool,
        uses_remote_event_source: bool,
    ) -> SpeechSource:
        if is_browser_mode:
            return _BaseSource(
                self._hooks,
                SpeechSourceCapabilities(
                    kind="browser_speech",
                    uses_backend_audio_capture=False,
                    uses_browser_worker=True,
                    uses_remote_audio_source=False,
                    uses_remote_event_source=False,
                ),
                name="BrowserSpeechSource",
            )
        if uses_remote_event_source:
            return _BaseSource(
                self._hooks,
                SpeechSourceCapabilities(
                    kind="remote_controller",
                    uses_backend_audio_capture=False,
                    uses_browser_worker=False,
                    uses_remote_audio_source=False,
                    uses_remote_event_source=True,
                ),
                name="RemoteControllerSpeechSource",
            )
        if uses_remote_audio_source:
            return _BaseSource(
                self._hooks,
                SpeechSourceCapabilities(
                    kind="remote_worker",
                    uses_backend_audio_capture=False,
                    uses_browser_worker=False,
                    uses_remote_audio_source=True,
                    uses_remote_event_source=False,
                ),
                name="RemoteWorkerSpeechSource",
            )
        return _BaseSource(
            self._hooks,
            SpeechSourceCapabilities(
                kind="local_parakeet",
                uses_backend_audio_capture=True,
                uses_browser_worker=False,
                uses_remote_audio_source=False,
                uses_remote_event_source=False,
            ),
            name="LocalParakeetSpeechSource",
        )


__all__ = ["SpeechSourceFactory", "_Hooks"]

