from __future__ import annotations

from typing import Awaitable, Callable

from backend.core.runtime.output_fanout_controller import OutputFanoutController
from backend.core.runtime.subtitle_presentation_controller import SubtitlePresentationController
from backend.core.runtime.translation_runtime_controller import TranslationRuntimeController
from backend.models import TranscriptEvent


class TranscriptController:
    """
    Stage 7 controller: central handler for transcript events.

    Responsibilities:
    - publish transcript websocket event
    - route transcript into subtitle presentation
    - publish source partial/final to OBS captions
    - submit finalized phrases into translation pipeline
    """

    name = "transcript"

    def __init__(
        self,
        *,
        subtitle: SubtitlePresentationController,
        translation: TranslationRuntimeController,
        output: OutputFanoutController,
        publish_transcript: Callable[[TranscriptEvent], Awaitable[None]] | None = None,
        publish_source_event: Callable[[TranscriptEvent], Awaitable[None]] | None = None,
        default_source_lang: str = "auto",
    ) -> None:
        self._subtitle = subtitle
        self._translation = translation
        self._output = output
        self._publish_transcript = publish_transcript or self._output.publish_transcript
        self._publish_source_event = publish_source_event or self._output.publish_source_event
        self._default_source_lang = str(default_source_lang or "auto").strip().lower() or "auto"

    @staticmethod
    def _event_source_lang(event: TranscriptEvent, fallback: str) -> str:
        segment = event.segment
        lang = None
        if segment is not None:
            lang = getattr(segment, "source_lang", None)
        normalized = str(lang or fallback or "auto").strip().lower() or "auto"
        return normalized

    async def handle_event(self, event: TranscriptEvent) -> None:
        await self._publish_transcript(event)
        await self._subtitle.handle_transcript(event)
        await self._publish_source_event(event)

        if event.event == "final":
            source_lang = self._event_source_lang(event, self._default_source_lang)
            await self._translation.submit_final(
                sequence=int(event.sequence),
                source_text=str(event.text or ""),
                source_lang=source_lang,
            )

