from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from backend.core.pipeline_trace_log import pipeline_trace
from backend.core.pipeline_trace_helpers import audio_chunk_metrics
from backend.core.pipeline_trace_sampler import PipelineTraceSampler


@dataclass(slots=True)
class AudioCaptureController:
    """
    Owns AudioCapture start/stop and the stored instance.
    """

    create_capture: Callable[[], Any]
    stop_in_thread: Callable[[Any], Awaitable[None]]

    _device_id: str | None = None
    _capture: Any | None = None
    _read_sampler: PipelineTraceSampler = field(
        default_factory=lambda: PipelineTraceSampler(min_interval_ms=500.0)
    )

    def set_device_id(self, device_id: str | None) -> None:
        previous = self._device_id
        self._device_id = str(device_id) if device_id is not None else None
        if previous != self._device_id:
            pipeline_trace(
                "capture",
                "audio_capture_controller",
                "device_id_set",
                previous_device_id=previous,
                device_id=self._device_id,
                capture_open=self._capture is not None,
            )

    @property
    def capture(self) -> Any | None:
        return self._capture

    def start_if_needed(self) -> None:
        if self._capture is not None:
            pipeline_trace(
                "capture",
                "audio_capture_controller",
                "start_skipped_already_running",
                device_id=self._device_id,
            )
            return
        if self._device_id is None:
            pipeline_trace(
                "capture",
                "audio_capture_controller",
                "start_skipped_no_device_id",
            )
            return
        capture = self.create_capture()
        capture.start(device_id=self._device_id)
        self._capture = capture
        pipeline_trace(
            "capture",
            "audio_capture_controller",
            "capture_started",
            device_id=self._device_id,
            sample_rate=self.sample_rate,
        )

    async def stop_if_running(self) -> None:
        if self._capture is None:
            pipeline_trace(
                "capture",
                "audio_capture_controller",
                "stop_skipped_not_running",
            )
            return
        capture = self._capture
        self._capture = None
        pipeline_trace(
            "capture",
            "audio_capture_controller",
            "capture_stopping",
            device_id=self._device_id,
        )
        try:
            await self.stop_in_thread(capture)
            pipeline_trace(
                "capture",
                "audio_capture_controller",
                "capture_stopped",
                device_id=self._device_id,
            )
        except asyncio.CancelledError:
            raise

    async def read_chunk(self, timeout: float) -> Any | None:
        if self._capture is None:
            if self._read_sampler.should_emit("read_no_capture"):
                pipeline_trace(
                    "capture",
                    "audio_capture_controller",
                    "read_skipped_no_capture",
                    device_id=self._device_id,
                )
            return None
        chunk = await asyncio.to_thread(self._capture.read_chunk, float(timeout))
        if chunk is None:
            if self._read_sampler.should_emit("read_timeout"):
                pipeline_trace(
                    "capture",
                    "audio_capture_controller",
                    "read_timeout",
                    timeout_s=float(timeout),
                    device_id=self._device_id,
                )
            return None
        if self._read_sampler.should_emit("read_chunk"):
            pipeline_trace(
                "capture",
                "audio_capture_controller",
                "read_chunk",
                device_id=self._device_id,
                **audio_chunk_metrics(chunk),
            )
        return chunk

    @property
    def sample_rate(self) -> int | None:
        if self._capture is None:
            return None
        value = getattr(self._capture, "sample_rate", None)
        return int(value) if isinstance(value, (int, float)) else None

