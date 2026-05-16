from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.core.browser_asr_gateway import BrowserAsrGateway
from backend.core.runtime.browser_asr_trace import BrowserAsrTraceFields, log_basr, new_event_id
from backend.core.runtime.speech_source import SpeechSourceCapabilities
from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.timekeeping import perf_counter_clock
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
    - L3 overlap check on worker_message_sequence (per session+generation)
    """

    name = "BrowserSpeechSource"

    def __init__(
        self,
        *,
        gateway: BrowserAsrGateway,
        hooks: _BrowserHooks,
        structured_logger: StructuredRuntimeLogger | None = None,
    ) -> None:
        self._gateway = gateway
        self._hooks = hooks
        self._structured_logger = structured_logger
        self._clock = perf_counter_clock
        self._active_session_id: str | None = None
        self._active_generation_id: int = 0
        self._sequence_watermark: dict[str, int] = {}

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
        self._sequence_watermark.clear()

    async def stop(self) -> None:
        self._active_session_id = None
        self._active_generation_id = 0
        self._sequence_watermark.clear()

    async def browser_worker_connected(self) -> None:
        await self._hooks.browser_worker_connected()

    async def browser_worker_disconnected(self) -> None:
        await self._hooks.browser_worker_disconnected()

    async def update_browser_worker_status(self, payload: dict[str, Any]) -> None:
        await self._hooks.update_browser_worker_status(payload)

    def _seq_key(self, session_id: str | None, generation_id: int) -> str:
        return f"{session_id or ''}:{generation_id}"

    def _log_ingress_reject_speech_source(
        self,
        *,
        reject_code: str,
        trace: BrowserAsrTraceFields,
    ) -> None:
        log_basr(
            self._structured_logger,
            "browser_recognition",
            "ingress_rejected_speech_source",
            trace=trace,
            payload={"reject_code": reject_code, "ingress_layer": "speech_source"},
        )

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
        asr_operational_event_id = payload.get("asr_operational_event_id")
        causal_parent_asr_event_id = payload.get("causal_parent_asr_event_id")
        basr_mono_ingress_at = payload.get("basr_mono_ingress_at")
        transport_id = payload.get("transport_id")

        base_trace = BrowserAsrTraceFields(
            event_id=str(asr_operational_event_id or new_event_id()),
            causal_parent_id=str(causal_parent_asr_event_id).strip() if causal_parent_asr_event_id else None,
            generation_id=int(generation_id or 0) or None,
            session_id=str(session_id or "").strip() or None,
            transport_id=int(transport_id) if transport_id is not None else None,
            mono_ingress_at=float(basr_mono_ingress_at) if basr_mono_ingress_at is not None else None,
        )

        normalized_session_id = str(session_id or "").strip() or None
        normalized_generation_id = max(0, int(generation_id or 0))
        if normalized_session_id:
            if self._active_session_id and normalized_session_id != self._active_session_id:
                # Stale session.
                self._gateway.update_status(
                    {"stale_worker_events_ignored": self._gateway.diagnostics().stale_worker_events_ignored + 1}
                )
                self._log_ingress_reject_speech_source(reject_code="stale_session", trace=base_trace)
                return
            self._active_session_id = normalized_session_id
        if normalized_generation_id:
            if normalized_generation_id < self._active_generation_id:
                self._gateway.update_status(
                    {"stale_worker_events_ignored": self._gateway.diagnostics().stale_worker_events_ignored + 1}
                )
                self._log_ingress_reject_speech_source(reject_code="stale_generation", trace=base_trace)
                return
            self._active_generation_id = normalized_generation_id

        if worker_message_sequence is not None:
            sk = self._seq_key(normalized_session_id, normalized_generation_id)
            seq = int(worker_message_sequence)
            prev = self._sequence_watermark.get(sk, -1)
            if seq <= prev:
                self._log_ingress_reject_speech_source(reject_code="overlap_sequence", trace=base_trace)
                return
            self._sequence_watermark[sk] = seq

        self._hooks.note_worker_event()

        normalized_source_lang = str(source_lang or self._hooks.browser_source_lang() or "auto").strip().lower() or "auto"

        # Normalize final fallback.
        partial_text = str(partial or "").strip()
        final_text = str(final or "").strip()
        if is_final and not final_text and partial_text:
            final_text = partial_text

        normalized_client_segment_id = str(client_segment_id or "").strip() or None

        trace_kwargs = {
            "asr_operational_event_id": asr_operational_event_id,
            "causal_parent_asr_event_id": causal_parent_asr_event_id,
            "basr_mono_ingress_at": basr_mono_ingress_at,
            "transport_id": transport_id,
        }

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
                **trace_kwargs,
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
                **trace_kwargs,
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

