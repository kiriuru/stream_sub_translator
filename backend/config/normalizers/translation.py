from __future__ import annotations

from typing import Any

from backend.config.secrets import (
    normalize_google_translate_api_key,
    normalize_provider_secret,
    normalize_provider_text_value,
)
from backend.translation.base import SUPPORTED_TRANSLATION_PROVIDERS


_SUPPORTED_PROVIDERS = set(SUPPORTED_TRANSLATION_PROVIDERS)
_CANONICAL_SLOT_IDS = tuple(f"translation_{index}" for index in range(1, 6))


def normalize_provider_settings(payload: Any, *, defaults: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    if not isinstance(payload, dict):
        return defaults

    normalized: dict[str, dict[str, str]] = {}
    for provider_name, provider_defaults in defaults.items():
        current = payload.get(provider_name, {})
        if not isinstance(current, dict):
            current = {}
        normalized[provider_name] = {
            key: str(current.get(key, provider_defaults[key]))
            for key in provider_defaults
        }
        if provider_name == "google_translate_v2":
            normalized[provider_name]["api_key"] = normalize_google_translate_api_key(
                normalized[provider_name].get("api_key", "")
            )
        elif provider_name == "google_cloud_translation_v3":
            access_token_candidate = current.get("access_token", normalized[provider_name].get("access_token", ""))
            if not access_token_candidate:
                access_token_candidate = current.get("api_key", "")
            project_id_candidate = current.get("project_id", normalized[provider_name].get("project_id", ""))
            if not project_id_candidate:
                project_id_candidate = current.get("endpoint", "")
            location_candidate = current.get("location", normalized[provider_name].get("location", "global"))
            if not location_candidate:
                location_candidate = current.get("region", "global")
            normalized[provider_name]["project_id"] = normalize_provider_text_value(project_id_candidate)
            normalized[provider_name]["access_token"] = normalize_provider_secret(access_token_candidate)
            normalized[provider_name]["location"] = normalize_provider_text_value(location_candidate) or "global"
            normalized[provider_name]["model"] = normalize_provider_text_value(
                current.get("model", normalized[provider_name].get("model", ""))
            )
        else:
            for key in list(normalized[provider_name].keys()):
                value = normalized[provider_name][key]
                if key in {"api_key", "access_token"}:
                    normalized[provider_name][key] = normalize_provider_secret(value)
                else:
                    normalized[provider_name][key] = normalize_provider_text_value(value)
    return normalized


def _normalize_provider(raw_provider: Any, *, fallback: str) -> str:
    provider = str(raw_provider or fallback).strip()
    if provider not in _SUPPORTED_PROVIDERS:
        return fallback
    return provider


def _normalize_target_languages(raw_target_languages: Any, fallback_targets: Any) -> list[str]:
    target_languages = raw_target_languages if isinstance(raw_target_languages, list) else fallback_targets
    if not isinstance(target_languages, list):
        target_languages = ["en"]
    return [
        str(item).strip().lower()
        for item in target_languages
        if str(item).strip()
    ]


def _normalize_translation_lines(
    *,
    translation: dict[str, Any],
    fallback_provider: str,
    target_languages: list[str],
) -> list[dict[str, Any]]:
    raw_lines = translation.get("lines", [])
    normalized_lines: list[dict[str, Any]] = []

    if isinstance(raw_lines, list) and raw_lines:
        for index, raw_line in enumerate(raw_lines):
            if not isinstance(raw_line, dict):
                continue
            slot_id = str(raw_line.get("slot_id") or "").strip().lower()
            if slot_id not in _CANONICAL_SLOT_IDS:
                slot_id = _CANONICAL_SLOT_IDS[index] if index < len(_CANONICAL_SLOT_IDS) else ""
            target_lang = str(raw_line.get("target_lang") or "").strip().lower()
            if not slot_id or not target_lang:
                continue
            provider = _normalize_provider(raw_line.get("provider"), fallback=fallback_provider)
            normalized_lines.append(
                {
                    "slot_id": slot_id,
                    "enabled": bool(raw_line.get("enabled", True)),
                    "target_lang": target_lang,
                    "provider": provider,
                    "label": str(raw_line.get("label") or "").strip() or target_lang.upper(),
                }
            )

    if not normalized_lines:
        fallback_targets = target_languages or ["en"]
        normalized_lines = [
            {
                "slot_id": _CANONICAL_SLOT_IDS[index],
                "enabled": True,
                "target_lang": target_lang,
                "provider": fallback_provider,
                "label": target_lang.upper(),
            }
            for index, target_lang in enumerate(fallback_targets[: len(_CANONICAL_SLOT_IDS)])
        ]

    return normalized_lines[: len(_CANONICAL_SLOT_IDS)]


def _build_compat_target_languages(lines: list[dict[str, Any]]) -> list[str]:
    compat_targets: list[str] = []
    for line in lines:
        if not line.get("enabled", True):
            continue
        target_lang = str(line.get("target_lang") or "").strip().lower()
        if target_lang and target_lang not in compat_targets:
            compat_targets.append(target_lang)
    return compat_targets


def _normalize_translation_cache(payload: Any, *, defaults: dict[str, Any]) -> dict[str, Any]:
    cache_defaults = defaults.get("cache", {}) if isinstance(defaults.get("cache"), dict) else {}
    current = payload if isinstance(payload, dict) else {}
    enabled_default = bool(cache_defaults.get("enabled", True))
    persist_default = bool(cache_defaults.get("persist", True))
    # Respect explicit false from the client; only fall back to defaults when the key is absent.
    if "enabled" in current:
        enabled = bool(current.get("enabled"))
    else:
        enabled = enabled_default
    if "persist" in current:
        persist = bool(current.get("persist"))
    else:
        persist = persist_default
    try:
        raw_max = current.get("max_entries", cache_defaults.get("max_entries", 5000))
        max_entries = int(raw_max if raw_max is not None else 5000)
    except (TypeError, ValueError):
        max_entries = 5000
    max_entries = max(0, min(50000, max_entries))
    return {"enabled": enabled, "persist": persist, "max_entries": max_entries}


def _normalize_provider_limits(payload: Any) -> dict[str, Any]:
    """Preserve optional per-provider concurrency/rate limits (dispatcher)."""
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, Any] = {}
    for provider_name, cfg in payload.items():
        name = str(provider_name or "").strip()
        if not name or not isinstance(cfg, dict):
            continue
        inner: dict[str, Any] = {}
        for key, value in cfg.items():
            key_str = str(key or "").strip()
            if not key_str:
                continue
            inner[key_str] = value
        if inner:
            normalized[name] = inner
    return normalized


def normalize_translation_config(
    payload: Any,
    *,
    defaults: dict[str, Any],
    fallback_targets: Any,
) -> dict[str, Any]:
    translation = payload if isinstance(payload, dict) else {}
    provider = _normalize_provider(translation.get("provider", defaults["provider"]), fallback=defaults["provider"])
    target_languages = _normalize_target_languages(translation.get("target_languages", fallback_targets), fallback_targets)

    try:
        translation_timeout_ms = int(translation.get("timeout_ms", defaults["timeout_ms"]) or defaults["timeout_ms"])
    except (TypeError, ValueError):
        translation_timeout_ms = int(defaults["timeout_ms"])
    try:
        translation_queue_max_size = int(
            translation.get("queue_max_size", defaults["queue_max_size"]) or defaults["queue_max_size"]
        )
    except (TypeError, ValueError):
        translation_queue_max_size = int(defaults["queue_max_size"])
    try:
        translation_max_concurrent_jobs = int(
            translation.get("max_concurrent_jobs", defaults["max_concurrent_jobs"]) or defaults["max_concurrent_jobs"]
        )
    except (TypeError, ValueError):
        translation_max_concurrent_jobs = int(defaults["max_concurrent_jobs"])

    normalized_lines = _normalize_translation_lines(
        translation=translation,
        fallback_provider=provider,
        target_languages=target_languages,
    )
    compat_target_languages = _build_compat_target_languages(normalized_lines)

    cache = _normalize_translation_cache(translation.get("cache", {}), defaults=defaults)
    provider_limits = _normalize_provider_limits(translation.get("provider_limits", {}))

    return {
        "enabled": bool(translation.get("enabled", False)),
        "provider": provider,
        "target_languages": compat_target_languages or ["en"],
        "lines": normalized_lines,
        "timeout_ms": max(1000, min(60000, translation_timeout_ms)),
        "queue_max_size": max(1, min(64, translation_queue_max_size)),
        "max_concurrent_jobs": max(1, min(8, translation_max_concurrent_jobs)),
        "provider_settings": normalize_provider_settings(
            translation.get("provider_settings", {}),
            defaults=defaults["provider_settings"],
        ),
        "cache": cache,
        "provider_limits": provider_limits,
    }
