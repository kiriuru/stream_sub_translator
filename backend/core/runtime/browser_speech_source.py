from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.core.browser_asr_gateway import BrowserAsrGateway
from backend.core.runtime.speech_source import SpeechSourceCapabilities
from backend.models import TranscriptEvent


@dataclass(slots=True)
class _BrowserHooks:
    browser_worker_connected: Callable[[], Awaitable[None]]
    browser_worker_disconnected: Callable[[], Awaitable[None]]
    update_browser_worker_status: Callable[[dict[str, Any]], Awaitable[None]]
    build_partial_event: Callable[..., Awaitable[TranscriptEvent | None]]
    build_final_event: Callable[..., Awaitable[TranscriptEvent | None]]
    transcript_sink_partial: Callable[[TranscriptEvent], Awaitable[None]]
    transcript_sink_final: Callable[[TranscriptEvent], Awaitable[None]]
    browser_source_lang: Callable[[], str]
    note_worker_event: Callable[[], None]


class BrowserSpeechSource:
    """
    SpeechSource implementation for browser speech worker mode.

    Owns:
    - active worker session + generation tracking (stale event filtering)
    - BrowserAsrGateway note_partial/note_final instrumentation
    """

    name = "BrowserSpeechSource"

    def __init__(self, *, gateway: BrowserAsrGateway, hooks: _BrowserHooks) -> None:
        self._gateway = gateway
        self._hooks = hooks
        self._active_session_id: str | None = None
        self._active_generation_id: int = 0

    def capabilities(self) -> SpeechSourceCapabilities:
        return SpeechSourceCapabilities(
            kind="browser_speech",
            uses_backend_audio_capture=False,
            uses_browser_worker=True,
            uses_remote_audio_source=False,
            uses_remote_event_source=False,
        )

    async def start(self) -> None:
        self._active_session_id = None
        self._active_generation_id = 0

    async def stop(self) -> None:
        self._active_session_id = None
        self._active_generation_id = 0

    async def browser_worker_connected(self) -> None:
        await self._hooks.browser_worker_connected()

    async def browser_worker_disconnected(self) -> None:
        await self._hooks.browser_worker_disconnected()

    async def update_browser_worker_status(self, payload: dict[str, Any]) -> None:
        await self._hooks.update_browser_worker_status(payload)

    async def ingest_external_asr_update(self, **payload: Any) -> None:
        partial = str(payload.get("partial", "") or "")
        final = str(payload.get("final", "") or "")
        is_final = bool(payload.get("is_final", False))
        source_lang = payload.get("source_lang")
        generation_id = payload.get("generation_id")
        session_id = payload.get("session_id")
        client_segment_id = payload.get("client_segment_id")
        forced_final = bool(payload.get("forced_final", False))
        asr_result_created_at_ms = payload.get("asr_result_created_at_ms")
        worker_send_started_at_ms = payload.get("worker_send_started_at_ms")
        worker_message_sequence = payload.get("worker_message_sequence")
        backend_received_at_ms = payload.get("backend_received_at_ms")

        normalized_session_id = str(session_id or "").strip() or None
        normalized_generation_id = max(0, int(generation_id or 0))
        if normalized_session_id:
            if self._active_session_id and normalized_session_id != self._active_session_id:
                # Stale session.
                self._gateway.update_status(
                    {"stale_worker_events_ignored": self._gateway.diagnostics().stale_worker_events_ignored + 1}
                )
                return
            self._active_session_id = normalized_session_id
        if normalized_generation_id:
            if normalized_generation_id < self._active_generation_id:
                self._gateway.update_status(
                    {"stale_worker_events_ignored": self._gateway.diagnostics().stale_worker_events_ignored + 1}
                )
                return
            self._active_generation_id = normalized_generation_id

        self._hooks.note_worker_event()

        normalized_source_lang = str(source_lang or self._hooks.browser_source_lang() or "auto").strip().lower() or "auto"

        # Normalize final fallback.
        partial_text = str(partial or "").strip()
        final_text = str(final or "").strip()
        if is_final and not final_text and partial_text:
            final_text = partial_text

        normalized_client_segment_id = str(client_segment_id or "").strip() or None

        if partial_text and not is_final:
            event = await self._hooks.build_partial_event(
                partial_text=partial_text,
                source_lang=normalized_source_lang,
                client_segment_id=normalized_client_segment_id,
                forced_final=forced_final,
                asr_result_created_at_ms=asr_result_created_at_ms,
                worker_send_started_at_ms=worker_send_started_at_ms,
                worker_message_sequence=worker_message_sequence,
                worker_generation_id=normalized_generation_id or None,
                worker_session_id=normalized_session_id,
                backend_received_at_ms=backend_received_at_ms,
            )
            if event is None:
                return
            self._gateway.note_partial(
                text_len=len(partial_text),
                source_lang=normalized_source_lang,
                sequence=event.sequence,
            )
            await self._hooks.transcript_sink_partial(event)
            return

        if is_final and final_text:
            event = await self._hooks.build_final_event(
                final_text=final_text,
                source_lang=normalized_source_lang,
                client_segment_id=normalized_client_segment_id,
                forced_final=forced_final,
                asr_result_created_at_ms=asr_result_created_at_ms,
                worker_send_started_at_ms=worker_send_started_at_ms,
                worker_message_sequence=worker_message_sequence,
                worker_generation_id=normalized_generation_id or None,
                worker_session_id=normalized_session_id,
                backend_received_at_ms=backend_received_at_ms,
            )
            if event is None:
                return
            self._gateway.note_final(
                text_len=len(final_text),
                source_lang=normalized_source_lang,
                sequence=event.sequence,
            )
            await self._hooks.transcript_sink_final(event)

    async def ingest_remote_audio_chunk(self, payload: bytes) -> bool:
        _ = payload
        return False

    async def ingest_remote_transcript_event(self, payload: dict) -> bool:
        _ = payload
        return False

    async def ingest_remote_translation_event(self, payload: dict) -> bool:
        _ = payload
        return False


__all__ = ["BrowserSpeechSource"]

