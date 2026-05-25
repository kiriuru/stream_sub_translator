from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from backend.core.pipeline_trace_helpers import (
    PipelineTraceHeartbeat,
    audio_bytes_metrics,
    audio_chunk_metrics,
    text_outcome_metrics,
    vad_segment_metrics,
)
from backend.core.pipeline_trace_log import pipeline_trace
from backend.core.pipeline_trace_sampler import PipelineTraceSampler
from backend.core.runtime.segment_audio_enqueue import clear_segment_audio_enqueue_state, slice_segment_audio_delta
from backend.core.segment_queue import AsrWorkItem
from backend.models import TranscriptEvent, TranscriptSegment


@dataclass
class _CaptureLoopTrace:
    heartbeat: PipelineTraceHeartbeat = field(default_factory=lambda: PipelineTraceHeartbeat(1000.0))
    wait_sampler: PipelineTraceSampler = field(default_factory=lambda: PipelineTraceSampler(min_interval_ms=2000.0))
    chunks_read: int = 0
    read_timeouts: int = 0
    vad_partial_segments: int = 0
    vad_final_segments: int = 0
    max_capture_level: float = 0.0

    def note_chunk(self, level: float | None) -> None:
        self.chunks_read += 1
        if level is not None:
            self.max_capture_level = max(self.max_capture_level, float(level))

    def note_timeout(self) -> None:
        self.read_timeouts += 1

    def emit_heartbeat(self, host: Any, *, reason: str, **extra: Any) -> None:
        metrics = host._metrics_controller.metrics
        pipeline_trace(
            "asyncio_capture_task",
            "local_asr_pipeline",
            "capture_heartbeat",
            reason=reason,
            device_id=host._device_id,
            capture_present=host._audio_capture is not None,
            chunks_read=self.chunks_read,
            read_timeouts=self.read_timeouts,
            max_capture_level=round(self.max_capture_level, 4),
            vad_partial_segments=self.vad_partial_segments,
            vad_final_segments=self.vad_final_segments,
            vad_segments_partial=int(getattr(metrics, "vad_segments_partial", 0) or 0),
            vad_segments_final=int(getattr(metrics, "vad_segments_final", 0) or 0),
            asr_queue_depth=host._segment_queue.qsize(),
            is_running=host._state.is_running,
            runtime_status=host._state.status,
            **extra,
        )


class LocalAsrPipeline:
    """
    Local microphone / remote-worker-audio capture → VAD → ASR queue → transcript events.

    Owned behavior extracted from RuntimeOrchestrator; the orchestrator remains the host
    for shared runtime state (VAD, queue, segment tracking, metrics, transcript routing).
    """

    name = "local_asr_pipeline"

    def __init__(self, host: Any) -> None:
        self._host = host

    async def run_capture_loop(self) -> None:
        host = self._host
        loop_trace = _CaptureLoopTrace()
        pipeline_trace(
            "asyncio_capture_task",
            "local_asr_pipeline",
            "capture_loop_enter",
            device_id=host._device_id,
            asr_generation=host._asr_runtime_generation,
            runtime_status=host._state.status,
        )
        try:
            while host._state.is_running:
                if host._uses_remote_audio_source():
                    remote_audio_queue = host._remote_audio_queue
                    if remote_audio_queue is None:
                        await asyncio.sleep(0.05)
                        continue
                    try:
                        chunk_data = await asyncio.wait_for(remote_audio_queue.get(), timeout=0.25)
                    except asyncio.TimeoutError:
                        if host._remote_audio_last_chunk_monotonic is not None:
                            host._record_metrics(
                                remote_audio_last_chunk_age_ms=(
                                    time.perf_counter() - host._remote_audio_last_chunk_monotonic
                                )
                                * 1000.0
                            )
                        continue
                    if not chunk_data:
                        continue
                    host._record_metrics(remote_audio_last_chunk_age_ms=0.0)
                else:
                    if host._audio_capture is None:
                        if loop_trace.wait_sampler.should_emit("capture_wait_no_audio"):
                            pipeline_trace(
                                "asyncio_capture_task",
                                "local_asr_pipeline",
                                "capture_wait_no_audio",
                                device_id=host._device_id,
                                local_device_id=host._local_audio_device_id,
                                runtime_status=host._state.status,
                            )
                        if loop_trace.heartbeat.due():
                            loop_trace.emit_heartbeat(host, reason="no_capture_instance")
                        await asyncio.sleep(0.05)
                        continue
                    chunk = await host._audio_capture_ctl.read_chunk(0.25)
                    if chunk is None:
                        loop_trace.note_timeout()
                        if loop_trace.heartbeat.due():
                            loop_trace.emit_heartbeat(host, reason="read_timeout")
                        continue
                    chunk_level = getattr(chunk, "level", None)
                    loop_trace.note_chunk(float(chunk_level) if chunk_level is not None else None)
                    chunk_data = chunk.data
                    if loop_trace.heartbeat.due():
                        loop_trace.emit_heartbeat(
                            host,
                            reason="chunk",
                            **audio_chunk_metrics(chunk),
                        )
                vad_started = time.perf_counter()
                segments = host._vad.process_chunk(chunk_data)
                vad_elapsed_ms = (time.perf_counter() - vad_started) * 1000.0
                host._record_metrics(
                    vad_ms=vad_elapsed_ms,
                    vad_dropped_segments=int(getattr(host._vad, "_segment_dropped_count", 0) or 0),
                )
                if not segments:
                    continue
                partial_segments = sum(1 for segment in segments if segment.kind == "partial")
                final_segments = sum(1 for segment in segments if segment.kind == "final")
                if partial_segments > 0:
                    host._increment_counter_metric("vad_segments_partial", partial_segments)
                    loop_trace.vad_partial_segments += partial_segments
                if final_segments > 0:
                    host._increment_counter_metric("vad_segments_final", final_segments)
                    loop_trace.vad_final_segments += final_segments

                for segment in segments:
                    pipeline_trace(
                        "asyncio_capture_task",
                        "local_asr_pipeline",
                        "vad_segment_emitted",
                        device_id=host._device_id,
                        vad_ms=round(vad_elapsed_ms, 2),
                        **vad_segment_metrics(segment),
                    )
                    segment_id, revision, started_now = host._assign_segment_tracking(segment.kind)
                    if started_now:
                        await host._broadcast_transcript_segment_event(
                            TranscriptEvent(
                                event="partial" if segment.kind == "partial" else "final",
                                lifecycle_event="segment_started",
                                text="",
                                device_id=host._device_id,
                                sequence=host._segment_state.sequence,
                                segment=TranscriptSegment(
                                    segment_id=segment_id,
                                    text="",
                                    is_partial=False,
                                    is_final=False,
                                    start_ms=0,
                                    end_ms=segment.duration_ms,
                                    source_lang=str(host.config_getter().get("source_lang", "auto")),
                                    provider=host._asr_engine.capabilities().provider_name,
                                    latency_ms=None,
                                    sequence=host._segment_state.sequence,
                                    revision=revision,
                                ),
                            )
                        )
                    prepared_audio = host._prepare_recognition_audio(segment.audio)
                    enqueue_audio = prepared_audio
                    audio_is_delta = False
                    if host._local_asr_delta_enqueue_enabled():
                        delta_audio, skip_enqueue = slice_segment_audio_delta(
                            segment_audio=prepared_audio,
                            segment_id=segment_id,
                            started_now=started_now,
                            queued_byte_len_by_segment=host._segment_queued_audio_len,
                        )
                        if segment.kind == "partial" and skip_enqueue:
                            continue
                        enqueue_audio = delta_audio
                        audio_is_delta = True

                    host._segment_queue.push(
                        AsrWorkItem(
                            kind=segment.kind,
                            audio=enqueue_audio,
                            duration_ms=segment.duration_ms,
                            generation=host._asr_runtime_generation,
                            segment_id=segment_id,
                            revision=revision,
                            vad_ms=vad_elapsed_ms,
                            audio_is_delta=audio_is_delta,
                            audio_segment_started_at_ms=int(time.time() * 1000),
                            vad_partial_ready_at_ms=int(time.time() * 1000),
                            asr_job_enqueued_at_ms=int(time.time() * 1000),
                        )
                    )
                    pipeline_trace(
                        "asyncio_capture_task",
                        "local_asr_pipeline",
                        "asr_job_enqueued",
                        kind=segment.kind,
                        segment_id=segment_id,
                        revision=revision,
                        generation=host._asr_runtime_generation,
                        audio_is_delta=audio_is_delta,
                        duration_ms=segment.duration_ms,
                        asr_queue_depth=host._segment_queue.qsize(),
                        **audio_bytes_metrics(enqueue_audio),
                    )
                    host._record_metrics(
                        asr_queue_depth=host._segment_queue.qsize(),
                        asr_partial_jobs_dropped=host._segment_queue.partial_jobs_dropped,
                        partial_jobs_coalesced=host._segment_queue.partial_jobs_coalesced,
                        finals_prioritized_count=host._segment_queue.finals_prioritized_count,
                    )
                    if segment.kind == "final":
                        clear_segment_audio_enqueue_state(host._segment_queued_audio_len, segment_id=segment_id)
                        host._segment_state.clear_active_segment()
        except asyncio.CancelledError:
            pipeline_trace(
                "asyncio_capture_task",
                "local_asr_pipeline",
                "capture_loop_cancelled",
                device_id=host._device_id,
            )
            raise
        except Exception as exc:
            pipeline_trace(
                "asyncio_capture_task",
                "local_asr_pipeline",
                "capture_loop_error",
                device_id=host._device_id,
                error=str(exc),
            )
            await host._safe_stop_audio()
            await host._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=host._state.started_at_utc,
                last_error=str(exc),
            )
        finally:
            pipeline_trace(
                "asyncio_capture_task",
                "local_asr_pipeline",
                "capture_loop_exit",
                device_id=host._device_id,
                chunks_read=loop_trace.chunks_read,
                read_timeouts=loop_trace.read_timeouts,
            )

    async def run_asr_loop(self) -> None:
        host = self._host
        pipeline_trace(
            "asyncio_asr_task",
            "local_asr_pipeline",
            "asr_loop_enter",
            asr_generation=host._asr_runtime_generation,
            runtime_status=host._state.status,
        )
        try:
            while host._state.is_running:
                work_item = await asyncio.to_thread(host._segment_queue.pop, 0.25)
                if work_item is None:
                    continue
                host._record_metrics(
                    asr_queue_depth=host._segment_queue.qsize(),
                    asr_partial_jobs_dropped=host._segment_queue.partial_jobs_dropped,
                    partial_jobs_coalesced=host._segment_queue.partial_jobs_coalesced,
                    finals_prioritized_count=host._segment_queue.finals_prioritized_count,
                )
                if work_item.generation != host._asr_runtime_generation:
                    host._record_metrics(
                        stale_partial_jobs_dropped=int(host._metrics_controller.metrics.stale_partial_jobs_dropped or 0)
                        + 1
                    )
                    pipeline_trace(
                        "asyncio_asr_task",
                        "local_asr_pipeline",
                        "asr_job_stale_generation",
                        job_generation=work_item.generation,
                        active_generation=host._asr_runtime_generation,
                        kind=work_item.kind,
                        segment_id=work_item.segment_id,
                    )
                    continue

                pipeline_trace(
                    "asyncio_asr_task",
                    "local_asr_pipeline",
                    "asr_job_started",
                    kind=work_item.kind,
                    segment_id=work_item.segment_id,
                    revision=work_item.revision,
                    generation=work_item.generation,
                    **audio_bytes_metrics(work_item.audio),
                )
                await host._set_runtime_state(
                    is_running=True,
                    status="transcribing",
                    started_at_utc=host._state.started_at_utc,
                )
                host._in_flight_transcribe_count += 1
                host._record_metrics(in_flight_transcribe_count=host._in_flight_transcribe_count)
                transcribe_started_at_ms = int(time.time() * 1000)
                try:
                    result = await asyncio.to_thread(
                        host._asr_engine.run,
                        work_item.audio,
                        is_final=work_item.kind == "final",
                        segment_id=work_item.segment_id or None,
                        audio_is_delta=work_item.audio_is_delta,
                    )
                finally:
                    transcribe_done_at_ms = int(time.time() * 1000)
                    host._in_flight_transcribe_count = max(0, host._in_flight_transcribe_count - 1)
                    host._record_metrics(in_flight_transcribe_count=host._in_flight_transcribe_count)
                if work_item.generation != host._asr_runtime_generation or not host._state.is_running:
                    host._record_metrics(
                        asr_stale_results_ignored=int(host._metrics_controller.metrics.asr_stale_results_ignored or 0)
                        + 1,
                    )
                    pipeline_trace(
                        "asyncio_asr_task",
                        "local_asr_pipeline",
                        "asr_result_stale",
                        kind=work_item.kind,
                        segment_id=work_item.segment_id,
                        is_running=host._state.is_running,
                        job_generation=work_item.generation,
                        active_generation=host._asr_runtime_generation,
                    )
                    continue
                now_monotonic = time.perf_counter()
                total_elapsed_ms = (now_monotonic - work_item.created_at_monotonic) * 1000.0
                transcribe_ms = max(0.0, float(transcribe_done_at_ms - transcribe_started_at_ms))
                queue_wait_ms = max(0.0, total_elapsed_ms - float(work_item.vad_ms) - transcribe_ms)
                asr_elapsed_ms = max(0.0, total_elapsed_ms - float(work_item.vad_ms) - queue_wait_ms)
                host._record_metrics(
                    vad_to_asr_enqueue_ms=float(work_item.vad_ms),
                    asr_queue_wait_ms=queue_wait_ms,
                    asr_transcribe_ms=transcribe_ms,
                )
                if work_item.kind == "final":
                    host._record_metrics(
                        vad_ms=work_item.vad_ms,
                        asr_final_ms=max(0.0, asr_elapsed_ms),
                        total_ms=total_elapsed_ms,
                    )
                else:
                    host._record_metrics(
                        vad_ms=work_item.vad_ms,
                        asr_partial_ms=max(0.0, asr_elapsed_ms),
                        total_ms=total_elapsed_ms,
                    )
                host._next_sequence()
                text = result.final if work_item.kind == "final" else result.partial
                pipeline_trace(
                    "asyncio_asr_task",
                    "local_asr_pipeline",
                    "asr_job_done",
                    kind=work_item.kind,
                    segment_id=work_item.segment_id,
                    revision=work_item.revision,
                    queue_wait_ms=round(queue_wait_ms, 2),
                    transcribe_ms=round(transcribe_ms, 2),
                    total_ms=round(total_elapsed_ms, 2),
                    **text_outcome_metrics(text),
                    **audio_bytes_metrics(work_item.audio),
                )
                if text:
                    if host._should_drop_short_hallucination(
                        text=text,
                        duration_ms=work_item.duration_ms,
                        is_final=work_item.kind == "final",
                    ):
                        if work_item.kind == "partial":
                            host._increment_metric("suppressed_partial_updates")
                        else:
                            host._clear_partial_tracking(work_item.segment_id)
                        await host._set_runtime_state(
                            is_running=True,
                            status="listening",
                            started_at_utc=host._state.started_at_utc,
                        )
                        continue
                    if work_item.kind == "partial":
                        segment_id = work_item.segment_id or ""
                        if not host._should_emit_partial(segment_id, text):
                            host._increment_metric("suppressed_partial_updates")
                            await host._set_runtime_state(
                                is_running=True,
                                status="listening",
                                started_at_utc=host._state.started_at_utc,
                            )
                            continue
                        host._mark_partial_emitted(segment_id, text)

                    lifecycle_event = "segment_finalized" if work_item.kind == "final" else "partial_updated"
                    segment = host._build_transcript_segment(
                        work_item=work_item,
                        text=text,
                        latency_ms=max(0.0, asr_elapsed_ms),
                    )
                    segment = segment.model_copy(
                        update={
                            "audio_segment_started_at_ms": work_item.audio_segment_started_at_ms,
                            "vad_partial_ready_at_ms": work_item.vad_partial_ready_at_ms,
                            "parakeet_transcribe_started_at_ms": transcribe_started_at_ms,
                            "parakeet_transcribe_done_at_ms": transcribe_done_at_ms,
                            "provider_result_created_at_ms": int(time.time() * 1000),
                        }
                    )
                    transcript_event = TranscriptEvent(
                        event=work_item.kind,
                        text=text,
                        device_id=host._device_id,
                        sequence=host._segment_state.sequence,
                        lifecycle_event=lifecycle_event,
                        segment=segment,
                    )
                    if work_item.kind == "final":
                        host._increment_metric("finals_emitted")
                        host._clear_partial_tracking(work_item.segment_id)
                        await host._transcript.handle_event(transcript_event)
                    else:
                        await host._transcript.handle_event(transcript_event)
                        host._increment_metric("partial_updates_emitted")
                elif work_item.kind == "final":
                    host._clear_partial_tracking(work_item.segment_id)
                else:
                    pipeline_trace(
                        "asyncio_asr_task",
                        "local_asr_pipeline",
                        "asr_empty_result",
                        kind=work_item.kind,
                        segment_id=work_item.segment_id,
                        revision=work_item.revision,
                        duration_ms=work_item.duration_ms,
                        **audio_bytes_metrics(work_item.audio),
                    )
                await host._set_listening_if_current("transcribing", broadcast=False)
        except asyncio.CancelledError:
            pipeline_trace("asyncio_asr_task", "local_asr_pipeline", "asr_loop_cancelled")
            raise
        except Exception as exc:
            pipeline_trace(
                "asyncio_asr_task",
                "local_asr_pipeline",
                "asr_loop_error",
                error=str(exc),
            )
            await host._safe_stop_audio()
            await host._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=host._state.started_at_utc,
                last_error=str(exc),
            )
        finally:
            pipeline_trace("asyncio_asr_task", "local_asr_pipeline", "asr_loop_exit")
