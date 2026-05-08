from __future__ import annotations

from typing import Awaitable, Callable

from backend.core.subtitle_router import SubtitleRouter
from backend.models import SubtitlePayloadEvent, TranscriptEvent, TranslationEvent
from backend.ws_manager import WebSocketManager


class SubtitlePresentationController:
    """
    Stage 4 controller: thin wrapper around SubtitleRouter.

    This preserves behavior while making RuntimeOrchestrator depend on a controller surface
    instead of the raw router object.
    """

    name = "subtitle_presentation"

    def __init__(
        self,
        ws_manager: WebSocketManager,
        config_getter: Callable[[], dict],
        completed_callback: Callable[[dict], None] | None = None,
        presentation_callback: Callable[[SubtitlePayloadEvent], Awaitable[None]] | None = None,
    ) -> None:
        self._router = SubtitleRouter(
            ws_manager,
            config_getter,
            completed_callback=completed_callback,
            presentation_callback=presentation_callback,
        )

    async def reset(self) -> None:
        await self._router.reset()

    async def handle_transcript(self, event: TranscriptEvent) -> None:
        await self._router.handle_transcript(event)

    async def handle_translation(self, event: TranslationEvent) -> None:
        await self._router.handle_translation(event)

    async def republish_latest(self) -> None:
        await self._router.republish_latest()

    async def clear_active_partial(self) -> None:
        await self._router.clear_active_partial()

    def diagnostic_counters(self) -> dict[str, int]:
        return self._router.diagnostic_counters()

    def is_sequence_relevant_for_translation(self, sequence: int) -> bool:
        return self._router.is_sequence_relevant_for_translation(sequence)

    def is_sequence_relevant_for_presentation(self, sequence: int) -> bool:
        return self._router.is_sequence_relevant_for_presentation(sequence)

