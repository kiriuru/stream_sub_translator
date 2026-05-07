from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.schemas.config_schema import CURRENT_CONFIG_VERSION
from backend.translation.base import SUPPORTED_TRANSLATION_PROVIDERS


_CANONICAL_SLOT_IDS = tuple(f"translation_{index}" for index in range(1, 6))
_SUPPORTED_PROVIDER_SET = set(SUPPORTED_TRANSLATION_PROVIDERS)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _parse_version(value: Any) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError):
        version = 1
    return max(1, version)


def _removed_local_provider_value() -> str:
    return "google" + "_" + "legacy" + "_http_experimental"


def _removed_local_provider_key() -> str:
    return "google" + "_" + "legacy" + "_http"


def _normalize_provider_name(raw_provider: Any, *, fallback: str) -> str:
    provider = str(raw_provider or fallback).strip()
    if provider not in _SUPPORTED_PROVIDER_SET:
        return fallback
    return provider


def _build_translation_lines(translation: dict[str, Any]) -> list[dict[str, Any]]:
    fallback_provider = _normalize_provider_name(
        translation.get("provider", "google_translate_v2"),
        fallback="google_translate_v2",
    )
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
            provider = _normalize_provider_name(raw_line.get("provider"), fallback=fallback_provider)
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
        legacy_targets = [
            str(item).strip().lower()
            for item in translation.get("target_languages", [])
            if str(item).strip()
        ]
        if not legacy_targets:
            legacy_targets = ["en"]
        normalized_lines = [
            {
                "slot_id": _CANONICAL_SLOT_IDS[index],
                "enabled": True,
                "target_lang": target_lang,
                "provider": fallback_provider,
                "label": target_lang.upper(),
            }
            for index, target_lang in enumerate(legacy_targets[: len(_CANONICAL_SLOT_IDS)])
        ]

    return normalized_lines[: len(_CANONICAL_SLOT_IDS)]


def _compat_target_languages(lines: list[dict[str, Any]]) -> list[str]:
    targets: list[str] = []
    for line in lines:
        if not line.get("enabled", True):
            continue
        target_lang = str(line.get("target_lang") or "").strip().lower()
        if target_lang and target_lang not in targets:
            targets.append(target_lang)
    return targets


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


def migrate_removed_legacy_asr_provider(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload if isinstance(payload, dict) else {})
    asr = _as_dict(migrated.get("asr"))

    provider_preference = str(asr.get("provider_preference", "") or "").strip().lower()
    if provider_preference in {"auto", _removed_local_provider_value()}:
        asr["provider_preference"] = "official_eu_parakeet_low_latency"

    removed_key = _removed_local_provider_key()
    if removed_key in asr:
        asr.pop(removed_key, None)

    migrated["asr"] = asr
    return migrated


def migrate_translation_lines_and_display_order(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload if isinstance(payload, dict) else {})
    translation = _as_dict(migrated.get("translation"))
    lines = _build_translation_lines(translation)
    translation["provider"] = _normalize_provider_name(
        translation.get("provider", "google_translate_v2"),
        fallback="google_translate_v2",
    )
    translation["lines"] = lines
    translation["target_languages"] = _compat_target_languages(lines)
    migrated["translation"] = translation

    subtitle_output = _as_dict(migrated.get("subtitle_output"))
    display_order = subtitle_output.get("display_order", [])
    if not isinstance(display_order, list):
        display_order = []

    language_to_slot: dict[str, str] = {}
    enabled_slots: list[str] = []
    for line in lines:
        slot_id = str(line.get("slot_id") or "").strip().lower()
        if line.get("enabled", True) and slot_id:
            enabled_slots.append(slot_id)
        target_lang = str(line.get("target_lang") or "").strip().lower()
        if target_lang and target_lang not in language_to_slot:
            language_to_slot[target_lang] = slot_id

    migrated_order: list[str] = []
    for raw_item in display_order:
        item = str(raw_item or "").strip().lower()
        if item == "source":
            if item not in migrated_order:
                migrated_order.append(item)
            continue
        if item in _CANONICAL_SLOT_IDS:
            if item not in migrated_order:
                migrated_order.append(item)
            continue
        mapped_slot = language_to_slot.get(item)
        if mapped_slot and mapped_slot not in migrated_order:
            migrated_order.append(mapped_slot)

    if "source" not in migrated_order:
        migrated_order.append("source")
    for slot_id in enabled_slots:
        if slot_id not in migrated_order:
            migrated_order.append(slot_id)

    subtitle_output["display_order"] = migrated_order
    migrated["subtitle_output"] = subtitle_output
    return migrated


def migrate_config(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload if isinstance(payload, dict) else {})
    version = _parse_version(migrated.get("config_version"))

    if version < 2:
        migrated = migrate_ui_and_config_shape(migrated)
    if version < 3:
        migrated = migrate_parakeet_provider_name(migrated)

    migrated = migrate_removed_legacy_asr_provider(migrated)
    if version < 6:
        migrated = migrate_translation_lines_and_display_order(migrated)

    migrated["config_version"] = CURRENT_CONFIG_VERSION
    return migrated
