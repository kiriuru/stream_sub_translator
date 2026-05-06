from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.schemas.config_schema import CURRENT_CONFIG_VERSION


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _parse_version(value: Any) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError):
        version = 1
    return max(1, version)


def migrate_ui_and_config_shape(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload if isinstance(payload, dict) else {})

    ui = _as_dict(migrated.get("ui"))
    ui["language"] = str(ui.get("language", "") or "").strip().lower() if ui.get("language") is not None else ""
    migrated["ui"] = ui

    asr = _as_dict(migrated.get("asr"))
    migrated["asr"] = asr

    translation = _as_dict(migrated.get("translation"))
    if not translation.get("target_languages") and isinstance(migrated.get("targets"), list):
        translation["target_languages"] = list(migrated.get("targets") or [])
    migrated["translation"] = translation

    remote = _as_dict(migrated.get("remote"))
    remote["enabled"] = bool(remote.get("enabled", False))
    migrated["remote"] = remote
    return migrated


def migrate_parakeet_provider_name(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload if isinstance(payload, dict) else {})
    asr = _as_dict(migrated.get("asr"))
    provider_preference = str(asr.get("provider_preference", "") or "").strip().lower()
    if provider_preference == "official_eu_parakeet_realtime":
        asr["provider_preference"] = "official_eu_parakeet_low_latency"
    migrated["asr"] = asr
    return migrated


def migrate_google_legacy_http_shape(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload if isinstance(payload, dict) else {})
    asr = _as_dict(migrated.get("asr"))
    google_legacy_http = _as_dict(asr.get("google_legacy_http"))
    asr["google_legacy_http"] = {
        "enabled": bool(google_legacy_http.get("enabled", False)),
        "language": str(google_legacy_http.get("language", "ru-RU") or "ru-RU").strip() or "ru-RU",
        "profanity_filter": bool(google_legacy_http.get("profanity_filter", False)),
        "connect_timeout_ms": google_legacy_http.get("connect_timeout_ms", 10000),
        "send_timeout_ms": google_legacy_http.get("send_timeout_ms", 10000),
        "recv_timeout_ms": google_legacy_http.get("recv_timeout_ms", 30000),
        "max_queue_depth": google_legacy_http.get("max_queue_depth", 50),
        "reconnect_initial_ms": google_legacy_http.get("reconnect_initial_ms", 1000),
        "reconnect_max_ms": google_legacy_http.get("reconnect_max_ms", 30000),
        "endpoint_host": str(google_legacy_http.get("endpoint_host", "") or "").strip(),
        "pair_id_prefix": str(google_legacy_http.get("pair_id_prefix", "sst") or "sst").strip() or "sst",
    }
    migrated["asr"] = asr
    return migrated


def migrate_google_legacy_http_keyless_shape(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload if isinstance(payload, dict) else {})
    asr = _as_dict(migrated.get("asr"))
    google_legacy_http = _as_dict(asr.get("google_legacy_http"))
    asr["google_legacy_http"] = {
        "enabled": bool(google_legacy_http.get("enabled", False)),
        "language": str(google_legacy_http.get("language", "ru-RU") or "ru-RU").strip() or "ru-RU",
        "profanity_filter": bool(google_legacy_http.get("profanity_filter", False)),
        "connect_timeout_ms": google_legacy_http.get("connect_timeout_ms", 10000),
        "send_timeout_ms": google_legacy_http.get("send_timeout_ms", 10000),
        "recv_timeout_ms": google_legacy_http.get("recv_timeout_ms", 30000),
        "max_queue_depth": google_legacy_http.get("max_queue_depth", 50),
        "reconnect_initial_ms": google_legacy_http.get("reconnect_initial_ms", 1000),
        "reconnect_max_ms": google_legacy_http.get("reconnect_max_ms", 30000),
        "endpoint_host": str(google_legacy_http.get("endpoint_host", "") or "").strip(),
        "pair_id_prefix": str(google_legacy_http.get("pair_id_prefix", "sst") or "sst").strip() or "sst",
    }
    migrated["asr"] = asr
    return migrated


def migrate_config(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload if isinstance(payload, dict) else {})
    version = _parse_version(migrated.get("config_version"))

    if version < 2:
        migrated = migrate_ui_and_config_shape(migrated)
    if version < 3:
        migrated = migrate_parakeet_provider_name(migrated)
    if version < 4:
        migrated = migrate_google_legacy_http_shape(migrated)
    if version < 5:
        migrated = migrate_google_legacy_http_keyless_shape(migrated)

    migrated["config_version"] = CURRENT_CONFIG_VERSION
    return migrated
