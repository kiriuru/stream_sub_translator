from __future__ import annotations

from typing import Any


_CANONICAL_SLOT_IDS = tuple(f"translation_{index}" for index in range(1, 6))


def _enabled_slot_ids(translation_lines: list[dict[str, Any]]) -> list[str]:
    return [
        str(line.get("slot_id") or "").strip().lower()
        for line in translation_lines
        if line.get("enabled", True) and str(line.get("slot_id") or "").strip()
    ]


def _legacy_language_map(translation_lines: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in translation_lines:
        if not line.get("enabled", True):
            continue
        target_lang = str(line.get("target_lang") or "").strip().lower()
        slot_id = str(line.get("slot_id") or "").strip().lower()
        if target_lang and slot_id and target_lang not in mapping:
            mapping[target_lang] = slot_id
    return mapping


def normalize_display_order(*, display_order: list[Any], translation_lines: list[dict[str, Any]]) -> list[str]:
    enabled_slots = _enabled_slot_ids(translation_lines)
    language_to_slot = _legacy_language_map(translation_lines)
    normalized_order: list[str] = []

    for item in display_order:
        value = str(item).strip().lower()
        if value == "source":
            if value not in normalized_order:
                normalized_order.append(value)
            continue
        if value in enabled_slots:
            if value not in normalized_order:
                normalized_order.append(value)
            continue
        mapped_slot = language_to_slot.get(value)
        if mapped_slot and mapped_slot not in normalized_order:
            normalized_order.append(mapped_slot)

    if "source" not in normalized_order:
        normalized_order.append("source")
    for slot_id in enabled_slots:
        if slot_id not in normalized_order:
            normalized_order.append(slot_id)
    return normalized_order


def normalize_subtitle_output_config(payload: Any, *, translation_lines: list[dict[str, Any]]) -> dict[str, Any]:
    subtitle_output = payload if isinstance(payload, dict) else {}
    default_display_order = ["source", *_enabled_slot_ids(translation_lines)]
    display_order = subtitle_output.get("display_order", default_display_order)
    if not isinstance(display_order, list):
        display_order = default_display_order
    try:
        max_translation_languages = int(subtitle_output.get("max_translation_languages", 2) or 0)
    except (TypeError, ValueError):
        max_translation_languages = 2
    return {
        "show_source": bool(subtitle_output.get("show_source", True)),
        "show_translations": bool(subtitle_output.get("show_translations", True)),
        "max_translation_languages": max(0, min(5, max_translation_languages)),
        "display_order": normalize_display_order(
            display_order=display_order,
            translation_lines=translation_lines,
        ),
    }


def normalize_subtitle_lifecycle_config(
    payload: Any,
    *,
    defaults: dict[str, Any],
    fallback_realtime: dict[str, int] | None = None,
    fallback_realtime_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = payload if isinstance(payload, dict) else {}
    realtime = fallback_realtime if isinstance(fallback_realtime, dict) else (fallback_realtime_defaults or {})

    def clamp_int_value(raw: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = int(default)
        return max(minimum, min(maximum, value))

    pause_default = int(realtime.get("finalization_hold_ms", defaults["pause_to_finalize_ms"]))
    hard_max_default = int(realtime.get("max_segment_ms", defaults["hard_max_phrase_ms"]))
    completed_ttl_default = clamp_int_value(
        current.get("completed_block_ttl_ms", defaults["completed_block_ttl_ms"]),
        default=defaults["completed_block_ttl_ms"],
        minimum=500,
        maximum=20000,
    )
    source_ttl = clamp_int_value(
        current.get("completed_source_ttl_ms", completed_ttl_default),
        default=completed_ttl_default,
        minimum=500,
        maximum=20000,
    )
    translation_ttl = clamp_int_value(
        current.get("completed_translation_ttl_ms", completed_ttl_default),
        default=completed_ttl_default,
        minimum=500,
        maximum=20000,
    )

    return {
        "completed_block_ttl_ms": max(source_ttl, translation_ttl),
        "completed_source_ttl_ms": source_ttl,
        "completed_translation_ttl_ms": translation_ttl,
        "pause_to_finalize_ms": clamp_int_value(
            current.get("pause_to_finalize_ms", pause_default),
            default=pause_default,
            minimum=120,
            maximum=5000,
        ),
        "allow_early_replace_on_next_final": bool(
            current.get("allow_early_replace_on_next_final", defaults["allow_early_replace_on_next_final"])
        ),
        "sync_source_and_translation_expiry": bool(
            current.get("sync_source_and_translation_expiry", defaults["sync_source_and_translation_expiry"])
        ),
        "keep_completed_translation_during_active_partial": bool(
            current.get(
                "keep_completed_translation_during_active_partial",
                defaults["keep_completed_translation_during_active_partial"],
            )
        ),
        "hard_max_phrase_ms": clamp_int_value(
            current.get("hard_max_phrase_ms", hard_max_default),
            default=hard_max_default,
            minimum=1000,
            maximum=30000,
        ),
    }
