from __future__ import annotations

from typing import Any

from backend.core.runtime.output_fanout_coordinator import broadcast_event
from backend.core.runtime.runtime_state_controller import RuntimeStateController
from backend.models import SubtitlePayloadEvent, TranscriptEvent, TranslationEvent
from backend.ws_manager import WebSocketManager


class OutputFanoutController:
    """
    Stage 5 controller: centralizes outbound runtime/transcript/translation/subtitle-payload fanout.

    Runtime update broadcasts remain owned by RuntimeStateController; this controller delegates to it.
    """

    name = "output_fanout"

    def __init__(
        self,
        ws_manager: WebSocketManager,
        *,
        obs_caption_output: Any | None,
        state_controller: RuntimeStateController,
    ) -> None:
        self._ws_manager = ws_manager
        self._obs_caption_output = obs_caption_output
        self._state_controller = state_controller

    async def broadcast_runtime_update(self, state: Any) -> None:
        await self._state_controller.broadcast_runtime(state)

    async def apply_live_settings(self, config: dict[str, Any]) -> None:
        if self._obs_caption_output is None:
            return
        await self._obs_caption_output.apply_live_settings(config)

    async def publish_transcript(self, event: TranscriptEvent) -> None:
        await broadcast_event(
            self._ws_manager,
            channel="transcript_update",
            payload=self._state_controller.enrich("transcript_update", event.model_dump()),
        )

    async def publish_source_event(self, event: TranscriptEvent) -> None:
        if self._obs_caption_output is None:
            return
        await self._obs_caption_output.publish_source_event(event)

    async def publish_transcript_segment_event(self, event: TranscriptEvent) -> None:
        await broadcast_event(
            self._ws_manager,
            channel="transcript_segment_event",
            payload=self._state_controller.enrich("transcript_segment_event", event.model_dump()),
        )

    async def publish_translation(self, event: TranslationEvent) -> None:
        await broadcast_event(
            self._ws_manager,
            channel="translation_update",
            payload=self._state_controller.enrich("translation_update", event.model_dump()),
        )

    async def publish_subtitle_payload(self, payload: SubtitlePayloadEvent) -> None:
        if self._obs_caption_output is None:
            return
        await self._obs_caption_output.publish_subtitle_payload(payload)

