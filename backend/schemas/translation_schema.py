from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TranslationItem(SchemaModel):
    target_lang: str
    text: str
    provider: str
    cached: bool = False
    success: bool = True
    error: str | None = None


class TranslationEvent(SchemaModel):
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
    is_complete: bool = True


class TranslationDiagnostics(SchemaModel):
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
    queue_depth: int = 0
    jobs_started: int = 0
    jobs_cancelled: int = 0
    stale_results_dropped: int = 0
    last_queue_latency_ms: float | None = None
    last_provider_latency_ms: float | None = None
    last_runtime_reason: str | None = None


class TranslationRuntimeStatus(SchemaModel):
    enabled: bool = False
    provider: str | None = None
    ready: bool = False
    degraded_mode: bool = False
    status: str = "disabled"
    summary: str | None = None
    target_languages: list[str] = Field(default_factory=list)
    diagnostics: TranslationDiagnostics | None = None
