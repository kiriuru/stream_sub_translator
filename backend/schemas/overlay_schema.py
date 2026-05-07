from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ObsCaptionDiagnostics(SchemaModel):
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


class ObsCaptionsStatus(SchemaModel):
    enabled: bool = False
    active: bool = False
    connected: bool = False
    connection_state: str = "disabled"
    output_mode: str = "disabled"
    diagnostics: ObsCaptionDiagnostics | None = None


class OverlayRuntimeStatus(SchemaModel):
    preset: str = "single"
    compact: bool = False
    overlay_url: str | None = None
    show_source: bool = True
    show_translations: bool = True
    display_order: list[str] = Field(default_factory=list)


class SubtitleLineItem(SchemaModel):
    kind: Literal["source", "translation"]
    lang: str
    label: str
    text: str
    style_slot: str | None = None
    slot_id: str | None = None
    target_lang: str | None = None
    provider: str | None = None
    visible: bool = True
    success: bool = True
    error: str | None = None


class SubtitlePayloadEvent(SchemaModel):
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
