from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.asr_schema import AsrDiagnostics, AsrRuntimeStatus
from backend.schemas.diagnostics_schema import RemoteDiagnostics
from backend.schemas.overlay_schema import ObsCaptionDiagnostics, ObsCaptionsStatus, OverlayRuntimeStatus
from backend.schemas.translation_schema import TranslationDiagnostics, TranslationRuntimeStatus


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RuntimeMetrics(SchemaModel):
    vad_ms: float | None = None
    asr_partial_ms: float | None = None
    asr_final_ms: float | None = None
    translation_ms: float | None = None
    total_ms: float | None = None
    translation_queue_depth: int = 0
    translation_jobs_started: int = 0
    translation_jobs_cancelled: int = 0
    translation_stale_results_dropped: int = 0
    translation_queue_latency_ms: float | None = None
    translation_provider_latency_ms: float | None = None
    partial_updates_emitted: int = 0
    finals_emitted: int = 0
    suppressed_partial_updates: int = 0
    vad_dropped_segments: int = 0
    remote_audio_chunks_in: int = 0
    remote_audio_bytes_in: int = 0
    remote_audio_chunks_dropped: int = 0
    remote_audio_level_rms: float | None = None
    remote_audio_last_chunk_age_ms: float | None = None
    vad_segments_partial: int = 0
    vad_segments_final: int = 0
    runtime_events_emitted: int = 0
    runtime_events_stale_dropped: int = 0
    runtime_events_duplicate_suppressed: int = 0
    runtime_events_last_sequence: int = 0
    runtime_status_broadcast_count: int = 0
    runtime_status_duplicate_suppressed: int = 0
    runtime_status_heartbeat_sent: int = 0
    browser_worker_event_count: int = 0
    browser_worker_event_coalesced: int = 0
    overlay_stale_translation_suppressed: int = 0
    overlay_payload_mismatch_count: int = 0
    client_log_events_received: int = 0
    client_log_events_written: int = 0
    client_log_events_dropped: int = 0
    ws_events_connections_active: int = 0
    ws_events_broadcast_count: int = 0
    ws_events_send_failures: int = 0
    ws_events_dead_connections_removed: int = 0


class RuntimeStatus(SchemaModel):
    running: bool = False
    starting: bool = False
    stopping: bool = False
    degraded_mode: bool = False
    fallback_reason: str | None = None
    phase: Literal["idle", "starting", "listening", "transcribing", "translating", "error"] = "idle"
    started_at_utc: str | None = None
    last_error: str | None = None
    status_message: str | None = None
    asr: AsrRuntimeStatus = Field(default_factory=AsrRuntimeStatus)
    translation: TranslationRuntimeStatus = Field(default_factory=TranslationRuntimeStatus)
    overlay: OverlayRuntimeStatus = Field(default_factory=OverlayRuntimeStatus)
    obs_captions: ObsCaptionsStatus = Field(default_factory=ObsCaptionsStatus)
    metrics: RuntimeMetrics = Field(default_factory=RuntimeMetrics)
    remote: RemoteDiagnostics | None = None
    is_running: bool = False
    status: Literal["idle", "starting", "listening", "transcribing", "translating", "error"] = "idle"
    asr_diagnostics: AsrDiagnostics | None = None
    translation_diagnostics: TranslationDiagnostics | None = None
    obs_caption_diagnostics: ObsCaptionDiagnostics | None = None
    remote_diagnostics: RemoteDiagnostics | None = None


RuntimeState = RuntimeStatus


class RuntimeActionResponse(SchemaModel):
    ok: bool = True
    action: str
    runtime: RuntimeStatus


class RuntimeStartRequest(SchemaModel):
    device_id: str | None = None


class ObsUrlResponse(SchemaModel):
    overlay_url: str
