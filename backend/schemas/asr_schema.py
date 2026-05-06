from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class BrowserAsrDiagnostics(SchemaModel):
    worker_connected: bool = False
    browser_mode: str | None = None
    start_mode: str | None = None
    experimental: bool = False
    session_id: str | None = None
    generation_id: int = 0
    client_segment_id: str | None = None
    desired_running: bool | None = None
    pending_start: bool | None = None
    recognition_running: bool | None = None
    recognition_state: str | None = None
    supervisor_state: str | None = None
    effective_continuous_mode: str | None = None
    recognition_continuous: bool | None = None
    websocket_ready: bool | None = None
    audio_track_enabled: bool | None = None
    audio_track_live: bool | None = None
    audio_track_kind: str | None = None
    audio_track_ready_state: str | None = None
    audio_track_muted: bool | None = None
    audio_track_reused: bool | None = None
    audio_track_reopen_count: int = 0
    audio_track_start_attempts: int = 0
    audio_track_start_failures: int = 0
    fallback_to_default_start: bool | None = None
    fallback_used: bool | None = None
    last_start_error: str | None = None
    last_audio_track_error: str | None = None
    forced_final: bool | None = None
    last_partial_at_utc: str | None = None
    last_final_at_utc: str | None = None
    last_partial_age_ms: int | None = None
    last_final_age_ms: int | None = None
    last_error: str | None = None
    error_type: str | None = None
    rearm_count: int = 0
    restart_count: int = 0
    no_speech_count: int = 0
    network_error_count: int = 0
    watchdog_rearm_count: int = 0
    duplicate_partial_suppressed: int = 0
    duplicate_final_suppressed: int = 0
    late_forced_final_suppressed: int = 0
    degraded_reason: str | None = None
    visibility_state: str | None = None
    mic_track_ready_state: str | None = None
    mic_track_muted: bool | None = None
    mic_rms: float | None = None
    mic_active_recent_ms: int | None = None
    last_mic_activity_at: int | None = None
    last_status_reason: str | None = None
    last_rearm_delay_ms: int | None = None
    stopping_since_ms: int | None = None
    last_seen_at_ms: int | None = None
    browser_worker_last_seen_age_ms: int | None = None
    stale_worker_events_ignored: int = 0


class AsrDiagnostics(SchemaModel):
    provider: str
    provider_label: str | None = None
    provider_mode_kind: Literal["local_ai", "browser_speech", "backend_streaming", "unknown"] = "unknown"
    true_streaming: bool = False
    requested_provider: str | None = None
    requested_device_policy: str | None = None
    requested_device: str | None = None
    model_load_mode: str | None = None
    model_repo: str | None = None
    model_revision: str | None = None
    model_path: str | None = None
    model_integrity_state: str | None = None
    supports_gpu: bool = False
    supports_partials: bool = False
    supports_streaming: bool = False
    supports_word_timestamps: bool = False
    supports_timestamps: bool = False
    gpu_requested: bool = False
    gpu_available: bool = False
    cuda_available: bool = False
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
    provider_state: str | None = None
    stream_generation: int = 0
    desired_running: bool | None = None
    upstream_connected: bool | None = None
    downstream_connected: bool | None = None
    reconnect_count: int = 0
    audio_queue_depth: int = 0
    audio_chunks_sent: int = 0
    audio_chunks_dropped: int = 0
    stale_results_ignored: int = 0
    partials_received: int = 0
    finals_received: int = 0
    duplicate_partials_suppressed: int = 0
    duplicate_finals_suppressed: int = 0
    last_error: str | None = None
    last_error_kind: str | None = None
    last_partial_age_ms: int | None = None
    last_final_age_ms: int | None = None
    connect_timeout_ms: int | None = None
    send_timeout_ms: int | None = None
    recv_timeout_ms: int | None = None
    max_queue_depth: int | None = None
    endpoint_mode: str | None = None
    uses_google_cloud_api: bool | None = None
    requires_api_key: bool | None = None
    browser_worker: BrowserAsrDiagnostics | None = None


class AsrRuntimeStatus(SchemaModel):
    active_mode: str = "local"
    provider: str | None = None
    provider_label: str | None = None
    ready: bool = False
    true_streaming: bool = False
    supports_partials: bool = False
    degraded_mode: bool = False
    fallback_reason: str | None = None
    diagnostics: AsrDiagnostics | None = None
