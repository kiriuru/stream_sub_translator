from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(slots=True)
class RuntimeLifecycleCoordinator:
    """
    Stage 8 stepping stone: centralizes start/stop ordering of runtime controllers.

    This deliberately stays lightweight (callbacks instead of a rigid interface) to keep the refactor
    low-risk while reducing orchestration code in RuntimeOrchestrator.
    """

    start_translation: Callable[[], Awaitable[None]]
    stop_translation: Callable[[], Awaitable[None]]
    start_obs_captions: Callable[[], Awaitable[None]]
    stop_obs_captions: Callable[[], Awaitable[None]]
    apply_obs_settings: Callable[[], Awaitable[None]]
    reset_subtitles: Callable[[], Awaitable[None]]

    async def start(self) -> None:
        # Translation is used by TranscriptController early; start it first.
        await self.start_translation()
        await self.start_obs_captions()
        await self.apply_obs_settings()
        await self.reset_subtitles()

    async def stop(self) -> None:
        # Reset subtitles before shutting down translation to flush payloads deterministically.
        await self.reset_subtitles()
        await self.stop_translation()
        await self.stop_obs_captions()

