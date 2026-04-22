from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class RuntimeMetrics(BaseModel):
    vad_ms: float | None = None
    asr_partial_ms: float | None = None
    asr_final_ms: float | None = None
    translation_ms: float | None = None
    total_ms: float | None = None
    partial_updates_emitted: int = 0
    finals_emitted: int = 0
    suppressed_partial_updates: int = 0
    vad_dropped_segments: int = 0


class AsrDiagnostics(BaseModel):
    provider: str
    requested_provider: str | None = None
    requested_device_policy: str | None = None
    model_path: str | None = None
    supports_gpu: bool = False
    supports_partials: bool = False
    supports_streaming: bool = False
    supports_word_timestamps: bool = False
    gpu_requested: bool = False
    gpu_available: bool = False
    torch_version: str | None = None
    torch_built_with_cuda: bool = False
    torch_cuda_is_available: bool = False
    torch_cuda_version: str | None = None
    torch_device_count: int = 0
    first_gpu_name: str | None = None
    python_executable: str | None = None
    venv_path: str | None = None
    degraded_mode: bool = False
    fallback_reason: str | None = None
    cpu_fallback_reason: str | None = None
    selected_device: str | None = None
    selected_execution_provider: str | None = None
    partials_supported: bool = False
    sample_rate: int | None = None
    audio_frame_duration_ms: int | None = None
    vad_mode: int | None = None
    vad_partial_interval_ms: int | None = None
    vad_min_speech_ms: int | None = None
    vad_first_partial_min_speech_ms: int | None = None
    vad_silence_padding_ms: int | None = None
    vad_finalization_hold_ms: int | None = None
    vad_max_segment_ms: int | None = None
    vad_energy_gate_enabled: bool = False
    vad_min_rms_for_recognition: float | None = None
    vad_min_voiced_ratio: float | None = None
    realtime_chunk_window_ms: int | None = None
    realtime_chunk_overlap_ms: int | None = None
    partial_min_delta_chars: int | None = None
    partial_coalescing_ms: int | None = None
    recognition_noise_reduction_enabled: bool = False
    rnnoise_strength: int = 0
    rnnoise_available: bool = False
    rnnoise_active: bool = False
    rnnoise_backend: str | None = None
    rnnoise_uses_resample: bool = False
    rnnoise_input_sample_rate: int | None = None
    rnnoise_processing_sample_rate: int | None = None
    rnnoise_frame_size_samples: int | None = None
    rnnoise_message: str | None = None
    message: str | None = None
    runtime_initialized: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "stream-sub-translator"
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    asr_provider: str | None = None
    asr_ready: bool | None = None
    asr_message: str | None = None
    asr_diagnostics: AsrDiagnostics | None = None
    translation_diagnostics: "TranslationDiagnostics | None" = None
    obs_caption_diagnostics: "ObsCaptionDiagnostics | None" = None


class ClientLogEventRequest(BaseModel):
    channel: Literal["dashboard", "overlay", "browser_worker"]
    message: str
    source: str | None = None
    details: dict[str, Any] | None = None


class ClientLogEventResponse(BaseModel):
    ok: bool = True


class RuntimeState(BaseModel):
    is_running: bool = False
    status: Literal["idle", "starting", "listening", "transcribing", "translating", "error"] = "idle"
    started_at_utc: str | None = None
    last_error: str | None = None
    status_message: str | None = None
    asr_diagnostics: AsrDiagnostics | None = None
    translation_diagnostics: "TranslationDiagnostics | None" = None
    obs_caption_diagnostics: "ObsCaptionDiagnostics | None" = None
    metrics: RuntimeMetrics | None = None


class RuntimeActionResponse(BaseModel):
    ok: bool = True
    action: str
    runtime: RuntimeState


class RuntimeStartRequest(BaseModel):
    device_id: str | None = None


class ObsUrlResponse(BaseModel):
    overlay_url: str


class AudioInputDevice(BaseModel):
    id: str
    name: str
    is_default: bool = False
    max_input_channels: int = 0
    default_samplerate: float | None = None


class AudioInputsResponse(BaseModel):
    devices: list[AudioInputDevice]
    source: str = "sounddevice"


class TranscriptEvent(BaseModel):
    event: Literal["partial", "final"]
    text: str
    device_id: str | None = None
    sequence: int = 0
    lifecycle_event: Literal["segment_started", "partial_updated", "segment_finalized"] | None = None
    segment: "TranscriptSegment | None" = None


class TranscriptSegment(BaseModel):
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


class TranslationItem(BaseModel):
    target_lang: str
    text: str
    provider: str
    cached: bool = False
    success: bool = True
    error: str | None = None


class TranslationEvent(BaseModel):
    sequence: int
    source_text: str
    source_lang: str
    translations: list[TranslationItem]
    provider: str
    provider_group: str | None = None
    experimental: bool = False
    local_provider: bool = False
    used_default_prompt: bool = False
    status_message: str | None = None


class TranslationDiagnostics(BaseModel):
    enabled: bool = False
    provider: str | None = None
    provider_group: str | None = None
    experimental: bool = False
    local_provider: bool = False
    configured: bool = False
    ready: bool = False
    degraded: bool = False
    status: str = "disabled"
    summary: str = "Translation disabled."
    reason: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    target_languages: list[str] = Field(default_factory=list)
    provider_endpoint: str | None = None
    uses_default_prompt: bool = False


class ObsCaptionDiagnostics(BaseModel):
    enabled: bool = False
    output_mode: str = "disabled"
    host: str = "127.0.0.1"
    port: int = 4455
    password_configured: bool = False
    connection_state: Literal["disabled", "disconnected", "connecting", "connected", "auth_failed", "error"] = "disabled"
    send_partials: bool = True
    partial_throttle_ms: int = 250
    min_partial_delta_chars: int = 3
    final_replace_delay_ms: int = 0
    clear_after_ms: int = 2500
    avoid_duplicate_text: bool = True
    connected: bool = False
    active: bool = False
    stream_output_active: bool | None = None
    stream_output_reconnecting: bool | None = None
    native_caption_ready: bool = False
    native_caption_status: str | None = None
    transport: str = "obs-websocket"
    request_type: str = "SendStreamCaption"
    debug_request_type: str | None = None
    debug_text_input_enabled: bool = False
    debug_text_input_name: str | None = None
    debug_text_input_send_partials: bool = True
    reconnect_attempt_count: int = 0
    last_send_used_active_connection: bool = False
    last_send_waited_for_connection: bool = False
    last_error: str | None = None
    last_caption_text: str | None = None
    last_caption_sent_at_utc: str | None = None
    last_debug_text: str | None = None
    obs_websocket_version: str | None = None
    obs_studio_version: str | None = None


class SubtitleLineItem(BaseModel):
    kind: Literal["source", "translation"]
    lang: str
    label: str
    text: str
    style_slot: str | None = None
    visible: bool = True
    success: bool = True
    error: str | None = None


class SubtitlePayloadEvent(BaseModel):
    sequence: int = 0
    source_lang: str = "auto"
    source_text: str = ""
    provider: str | None = None
    preset: str = "single"
    compact: bool = False
    display_order: list[str] = Field(default_factory=list)
    show_source: bool = True
    show_translations: bool = True
    max_translation_languages: int = 0
    items: list[SubtitleLineItem] = Field(default_factory=list)
    visible_items: list[SubtitleLineItem] = Field(default_factory=list)
    style: dict[str, Any] = Field(default_factory=dict)
    lifecycle_state: Literal["idle", "partial_only", "completed_only", "completed_with_partial"] = "idle"
    completed_block_visible: bool = False
    completed_expires_at_utc: str | None = None
    active_partial_text: str = ""
    active_partial_sequence: int | None = None
    active_partial_source_lang: str | None = None
    line1: str = ""
    line2: str = ""


class SettingsSaveRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class SettingsSaveResponse(BaseModel):
    ok: bool = True
    saved_to: str
    payload: dict[str, Any] = Field(default_factory=dict)
    subtitle_style_presets: dict[str, Any] = Field(default_factory=dict)
    font_catalog: dict[str, Any] = Field(default_factory=dict)
    live_applied: bool = False


class SettingsLoadResponse(BaseModel):
    ok: bool = True
    payload: dict[str, Any]
    subtitle_style_presets: dict[str, Any] = Field(default_factory=dict)
    font_catalog: dict[str, Any] = Field(default_factory=dict)
    loaded_from: str


class ProfilePayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ProfileListResponse(BaseModel):
    profiles: list[str]


class ProfileResponse(BaseModel):
    name: str
    payload: dict[str, Any]


class ProfileWriteResponse(BaseModel):
    ok: bool = True
    name: str
    saved_to: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ProfileDeleteResponse(BaseModel):
    ok: bool = True
    name: str
    deleted: bool


class ExportFileInfo(BaseModel):
    name: str
    size_bytes: int
    modified_utc: str


class ExportsListResponse(BaseModel):
    exports: list[str] = Field(default_factory=list)
    files: list[ExportFileInfo] = Field(default_factory=list)
