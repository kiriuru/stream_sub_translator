from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from backend.core.pipeline_trace_log import pipeline_trace


@dataclass(slots=True)
class RuntimeLifecycleCoordinator:
    """
    Centralizes ordered runtime lifecycle (start/stop) across the full runtime surface.

    Still callback-based, but now defines the canonical order for *all* runtime-owned components,
    not only translation/OBS/subtitles.
    """

    # Pre-start / pre-stop bookkeeping
    pre_start: Callable[[], None]
    pre_stop: Callable[[], None]

    # Core runtime surfaces
    start_translation: Callable[[], Awaitable[None]]
    stop_translation: Callable[[], Awaitable[None]]
    start_obs_captions: Callable[[], Awaitable[None]]
    stop_obs_captions: Callable[[], Awaitable[None]]
    apply_obs_settings: Callable[[], Awaitable[None]]
    reset_subtitles: Callable[[], Awaitable[None]]

    # Speech source + audio/tasks
    select_speech_source: Callable[[], None]
    start_speech_source: Callable[[], Awaitable[None]]
    stop_speech_source: Callable[[], Awaitable[None]]

    # Runtime session/reset/engine lifecycle
    on_start_reset: Callable[[], None]
    start_session: Callable[[], str]
    capture_asr_mode_for_start: Callable[[], None]
    init_asr_runtime_if_needed: Callable[[], Awaitable[None]]
    unload_asr_runtime_state: Callable[[], Awaitable[None]]

    # Stop-time cleanup
    safe_stop_audio: Callable[[], Awaitable[None]]
    shutdown_remote_audio: Callable[[], Awaitable[None]]
    stop_session_cleanup: Callable[[], None]
    try_export_on_stop: Callable[[], str | None]
    broadcast_runtime: Callable[[], Awaitable[None]]
    clear_after_stop: Callable[[], None]

    async def _trace_phase(self, *, flow: str, phase: str, started_at: float, **fields: object) -> None:
        pipeline_trace(
            "runtime_lifecycle",
            "runtime_lifecycle_coordinator",
            f"{flow}_{phase}",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000.0, 2),
            **fields,
        )

    async def start(self) -> str:
        """
        Returns started_at_utc string from the session controller.
        """
        flow_started = time.perf_counter()
        pipeline_trace("runtime_lifecycle", "runtime_lifecycle_coordinator", "start_begin")
        self.pre_start()
        await self._trace_phase(flow="start", phase="pre_start", started_at=flow_started)
        self.select_speech_source()
        await self._trace_phase(flow="start", phase="select_speech_source", started_at=flow_started)

        # Translation is used by TranscriptController early; start it first.
        await self.start_translation()
        await self._trace_phase(flow="start", phase="start_translation", started_at=flow_started)
        await self.start_obs_captions()
        await self._trace_phase(flow="start", phase="start_obs_captions", started_at=flow_started)
        await self.apply_obs_settings()
        await self._trace_phase(flow="start", phase="apply_obs_settings", started_at=flow_started)
        await self.reset_subtitles()
        await self._trace_phase(flow="start", phase="reset_subtitles", started_at=flow_started)

        self.on_start_reset()
        await self._trace_phase(flow="start", phase="on_start_reset", started_at=flow_started)
        await self.init_asr_runtime_if_needed()
        await self._trace_phase(flow="start", phase="init_asr_runtime", started_at=flow_started)
        started_at = self.start_session()
        await self._trace_phase(flow="start", phase="start_session", started_at=flow_started, session_started_at=started_at)
        self.capture_asr_mode_for_start()
        await self._trace_phase(flow="start", phase="capture_asr_mode", started_at=flow_started)
        await self.start_speech_source()
        await self._trace_phase(flow="start", phase="start_speech_source", started_at=flow_started)
        pipeline_trace(
            "runtime_lifecycle",
            "runtime_lifecycle_coordinator",
            "start_complete",
            elapsed_ms=round((time.perf_counter() - flow_started) * 1000.0, 2),
            session_started_at=started_at,
        )
        return started_at

    async def stop(self) -> str | None:
        flow_started = time.perf_counter()
        pipeline_trace("runtime_lifecycle", "runtime_lifecycle_coordinator", "stop_begin")
        self.pre_stop()
        await self._trace_phase(flow="stop", phase="pre_stop", started_at=flow_started)

        await self.stop_speech_source()
        await self._trace_phase(flow="stop", phase="stop_speech_source", started_at=flow_started)
        await self.safe_stop_audio()
        await self._trace_phase(flow="stop", phase="safe_stop_audio", started_at=flow_started)

        # Reset subtitles before shutting down translation to flush payloads deterministically.
        await self.reset_subtitles()
        await self._trace_phase(flow="stop", phase="reset_subtitles", started_at=flow_started)
        await self.stop_translation()
        await self._trace_phase(flow="stop", phase="stop_translation", started_at=flow_started)
        await self.stop_obs_captions()
        await self._trace_phase(flow="stop", phase="stop_obs_captions", started_at=flow_started)

        export_error = self.try_export_on_stop()
        await self._trace_phase(
            flow="stop",
            phase="try_export_on_stop",
            started_at=flow_started,
            export_error=export_error,
        )
        await self.unload_asr_runtime_state()
        await self._trace_phase(flow="stop", phase="unload_asr_runtime", started_at=flow_started)
        await self.shutdown_remote_audio()
        await self._trace_phase(flow="stop", phase="shutdown_remote_audio", started_at=flow_started)
        self.stop_session_cleanup()
        await self._trace_phase(flow="stop", phase="stop_session_cleanup", started_at=flow_started)
        await self.broadcast_runtime()
        await self._trace_phase(flow="stop", phase="broadcast_runtime", started_at=flow_started)
        self.clear_after_stop()
        pipeline_trace(
            "runtime_lifecycle",
            "runtime_lifecycle_coordinator",
            "stop_complete",
            elapsed_ms=round((time.perf_counter() - flow_started) * 1000.0, 2),
            export_error=export_error,
        )
        return export_error

