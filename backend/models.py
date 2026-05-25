from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas import (
    AsrDiagnostics,
    AsrRuntimeStatus,
    BrowserAsrDiagnostics,
    ConfigSchema,
    HealthResponse,
    ObsCaptionDiagnostics,
    ObsCaptionsStatus,
    ObsUrlResponse,
    OverlayRuntimeStatus,
    ReleaseSyncStatus,
    RemoteDiagnostics,
    RemoteHeartbeatRequest,
    RemoteHeartbeatResponse,
    RemotePairCreateRequest,
    RemotePairCreateResponse,
    RemotePairVerifyRequest,
    RemotePairVerifyResponse,
    RemotePairingStatus,
    RemoteStateResponse,
    RuntimeActionResponse,
    RuntimeMetrics,
    RuntimeStartRequest,
    RuntimeState,
    RuntimeStatus,
    SubtitleLineItem,
    SubtitlePayloadEvent,
    TranslationDiagnostics,
    TranslationEvent,
    TranslationItem,
    TranslationRuntimeStatus,
    VersionInfoResponse,
)


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ClientLogEventRequest(SchemaModel):
    channel: Literal["dashboard", "overlay", "browser_worker"]
    message: str
    source: str | None = None
    details: dict[str, Any] | None = None


class ClientLogEventResponse(SchemaModel):
    ok: bool = True
    logged: bool = True
    reason: str | None = None


class UiTraceEventRequest(SchemaModel):
    surface: Literal["dashboard", "overlay", "browser_worker", "desktop"] = "dashboard"
    phase: str
    event: str
    fields: dict[str, Any] | None = None


class UiTraceEventResponse(SchemaModel):
    ok: bool = True
    logged: bool = True
    reason: str | None = None


class RemoteWorkerRuntimeActionResponse(SchemaModel):
    ok: bool = True
    action: Literal["start", "stop"]
    worker_url: str | None = None
    worker_runtime: RuntimeStatus | None = None
    error: str | None = None


class RemoteWorkerRuntimeStatusResponse(SchemaModel):
    ok: bool = True
    worker_url: str | None = None
    worker_runtime: RuntimeStatus | None = None
    error: str | None = None


class RemoteWorkerHealthResponse(SchemaModel):
    ok: bool = True
    worker_url: str | None = None
    health: dict[str, Any] | None = None
    error: str | None = None


class RemoteWorkerSettingsSyncResponse(SchemaModel):
    ok: bool = True
    worker_url: str | None = None
    synced_sections: list[str] = Field(default_factory=list)
    worker_translation_enabled: bool | None = None
    worker_target_languages: list[str] = Field(default_factory=list)
    worker_asr_mode: str | None = None
    error: str | None = None


class AudioInputDevice(SchemaModel):
    id: str
    name: str
    is_default: bool = False
    max_input_channels: int = 0
    default_samplerate: float | None = None


class AudioInputsResponse(SchemaModel):
    devices: list[AudioInputDevice]
    source: str = "sounddevice"


class TranscriptEvent(SchemaModel):
    event: Literal["partial", "final"]
    text: str
    device_id: str | None = None
    sequence: int = 0
    lifecycle_event: Literal["segment_started", "partial_updated", "segment_finalized"] | None = None
    segment: "TranscriptSegment | None" = None


class TranscriptSegment(SchemaModel):
    segment_id: str
    text: str
    is_partial: bool = False
    is_final: bool = False
    start_ms: int | None = None
    end_ms: int | None = None
    source_lang: str = "auto"
    provider: str | None = None
    latency_ms: float | None = None
    sequence: int = 0
    revision: int = 0
    asr_result_created_at_ms: int | None = None
    worker_send_started_at_ms: int | None = None
    worker_message_sequence: int | None = None
    worker_generation_id: int | None = None
    worker_session_id: str | None = None
    backend_received_at_ms: int | None = None
    backend_published_to_router_at_ms: int | None = None
    router_received_at_ms: int | None = None
    ws_broadcast_at_ms: int | None = None
    dashboard_received_at_ms: int | None = None
    audio_segment_started_at_ms: int | None = None
    vad_partial_ready_at_ms: int | None = None
    parakeet_transcribe_started_at_ms: int | None = None
    parakeet_transcribe_done_at_ms: int | None = None
    provider_result_created_at_ms: int | None = None
    # Domain B → Domain A reference (optional; not a merged causal graph).
    asr_operational_event_id: str | None = None
    causal_parent_asr_event_id: str | None = None
    # Domain C preview / lineage (optional reference to Domain B key).
    translation_preview_lineage_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SettingsSaveRequest(SchemaModel):
    payload: dict[str, Any]


class SettingsSaveResponse(SchemaModel):
    ok: bool = True
    saved_to: str
    payload: ConfigSchema
    subtitle_style_presets: dict[str, Any] = Field(default_factory=dict)
    font_catalog: dict[str, Any] = Field(default_factory=dict)
    live_applied: bool = False


class SettingsLoadResponse(SchemaModel):
    ok: bool = True
    payload: ConfigSchema
    subtitle_style_presets: dict[str, Any] = Field(default_factory=dict)
    font_catalog: dict[str, Any] = Field(default_factory=dict)
    loaded_from: str


class ProfilePayload(SchemaModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ProfileListResponse(SchemaModel):
    profiles: list[str]


class ProfileResponse(SchemaModel):
    name: str
    payload: ConfigSchema


class ProfileWriteResponse(SchemaModel):
    ok: bool = True
    name: str
    saved_to: str
    payload: ConfigSchema


class ProfileDeleteResponse(SchemaModel):
    ok: bool = True
    name: str
    deleted: bool


class ExportFileInfo(SchemaModel):
    name: str
    size_bytes: int
    modified_utc: str


class ExportsListResponse(SchemaModel):
    exports: list[str] = Field(default_factory=list)
    files: list[ExportFileInfo] = Field(default_factory=list)
