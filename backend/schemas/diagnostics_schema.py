from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.asr_schema import AsrDiagnostics
from backend.schemas.overlay_schema import ObsCaptionDiagnostics
from backend.schemas.translation_schema import TranslationDiagnostics


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ReleaseSyncStatus(SchemaModel):
    provider: str = "github_releases"
    enabled: bool = False
    github_repo: str | None = None
    release_channel: str = "stable"
    latest_known_version: str | None = None
    last_checked_utc: str | None = None
    update_available: bool = False
    check_supported: bool = False
    check_active: bool = False
    message: str | None = None


class VersionInfoResponse(SchemaModel):
    ok: bool = True
    current_version: str
    release_track: str = "stable"
    sync: ReleaseSyncStatus


class RemoteDiagnostics(SchemaModel):
    enabled: bool = False
    configured_role: Literal["disabled", "controller", "worker"] = "disabled"
    effective_role: Literal["disabled", "controller", "worker"] = "disabled"
    lan_bind_enabled: bool = False
    lan_bind_host: str = "127.0.0.1"
    lan_bind_port: int = 8765
    worker_url: str | None = None
    session_id: str | None = None
    pair_code_set: bool = False
    message: str | None = None


class HealthResponse(SchemaModel):
    status: str = "ok"
    service: str = "stream-sub-translator"
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    app_version: str | None = None
    release_sync: ReleaseSyncStatus | None = None
    asr_provider: str | None = None
    asr_ready: bool | None = None
    asr_message: str | None = None
    asr_diagnostics: AsrDiagnostics | None = None
    translation_diagnostics: TranslationDiagnostics | None = None
    obs_caption_diagnostics: ObsCaptionDiagnostics | None = None
    remote_diagnostics: RemoteDiagnostics | None = None


class RemotePairingStatus(SchemaModel):
    session_id: str | None = None
    expires_at_utc: str | None = None
    is_active: bool = False
    controller_last_seen_utc: str | None = None
    worker_last_seen_utc: str | None = None
    controller_online: bool = False
    worker_online: bool = False


class RemoteStateResponse(SchemaModel):
    ok: bool = True
    remote: RemoteDiagnostics
    pairing: RemotePairingStatus | None = None


class RemotePairCreateRequest(SchemaModel):
    ttl_seconds: int = 43200


class RemotePairCreateResponse(SchemaModel):
    ok: bool = True
    session_id: str
    pair_code: str
    expires_at_utc: str
    pairing: RemotePairingStatus


class RemotePairVerifyRequest(SchemaModel):
    session_id: str
    pair_code: str


class RemotePairVerifyResponse(SchemaModel):
    ok: bool = True
    accepted: bool
    reason: str | None = None
    pairing: RemotePairingStatus | None = None


class RemoteHeartbeatRequest(SchemaModel):
    session_id: str
    role: Literal["controller", "worker"]


class RemoteHeartbeatResponse(SchemaModel):
    ok: bool = True
    accepted: bool = True
    reason: str | None = None
    pairing: RemotePairingStatus | None = None
