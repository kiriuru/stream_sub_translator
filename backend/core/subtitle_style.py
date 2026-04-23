from __future__ import annotations

from copy import deepcopy
from typing import Any


LINE_SLOT_NAMES: tuple[str, ...] = (
    "source",
    "translation_1",
    "translation_2",
    "translation_3",
    "translation_4",
    "translation_5",
)

TRANSLATION_LINE_SLOT_NAMES: tuple[str, ...] = LINE_SLOT_NAMES[1:]

_BASE_STYLE_DEFAULTS: dict[str, Any] = {
    "font_family": '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
    "font_size_px": 30,
    "font_weight": 700,
    "fill_color": "#ffffff",
    "stroke_color": "#000000",
    "stroke_width_px": 2,
    "shadow_color": "#000000",
    "shadow_blur_px": 10,
    "shadow_offset_x_px": 0,
    "shadow_offset_y_px": 3,
    "background_color": "#000000",
    "background_opacity": 0,
    "background_padding_x_px": 12,
    "background_padding_y_px": 4,
    "background_radius_px": 10,
    "line_spacing_em": 1.15,
    "letter_spacing_em": 0.0,
    "text_align": "center",
    "line_gap_px": 8,
    "effect": "none",
}

_OVERRIDE_ALLOWED_FIELDS = tuple(_BASE_STYLE_DEFAULTS.keys())


def _empty_slot_override() -> dict[str, Any]:
    return {"enabled": False}


def _clone_slot_overrides(
    overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    current = overrides if isinstance(overrides, dict) else {}
    normalized: dict[str, dict[str, Any]] = {}
    for slot_name in LINE_SLOT_NAMES:
        normalized[slot_name] = {
            "enabled": bool((current.get(slot_name) or {}).get("enabled", False)),
            **deepcopy(current.get(slot_name) or {}),
        }
    return normalized


def _preset_style(
    *,
    preset: str,
    label: str,
    description: str,
    base: dict[str, Any],
    line_slots: dict[str, dict[str, Any]] | None = None,
    recommended_max_visible_lines: int | None = None,
) -> dict[str, Any]:
    return {
        "preset": preset,
        "label": label,
        "description": description,
        "built_in": True,
        "recommended_max_visible_lines": recommended_max_visible_lines,
        "base": {**deepcopy(_BASE_STYLE_DEFAULTS), **deepcopy(base)},
        "line_slots": _clone_slot_overrides(line_slots),
    }


_STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "clean_default": _preset_style(
        preset="clean_default",
        label="Clean Default",
        description="Balanced white subtitles with readable outline and no extra effects.",
        base={},
    ),
    "streamer_bold": _preset_style(
        preset="streamer_bold",
        label="Streamer Bold",
        description="Larger, stronger subtitle look for busy gameplay scenes.",
        base={
            "font_family": '"Trebuchet MS", "Segoe UI", sans-serif',
            "font_size_px": 34,
            "font_weight": 800,
            "stroke_width_px": 3,
            "shadow_blur_px": 14,
            "shadow_offset_y_px": 4,
            "background_opacity": 18,
            "background_padding_x_px": 14,
            "background_padding_y_px": 6,
            "background_radius_px": 12,
            "line_gap_px": 10,
        },
    ),
    "dual_tone": _preset_style(
        preset="dual_tone",
        label="Dual Tone",
        description="Distinct source and translation colors while keeping one coherent layout.",
        base={
            "font_family": '"Verdana", "Segoe UI", sans-serif',
            "font_size_px": 30,
            "stroke_width_px": 2,
            "shadow_blur_px": 12,
            "background_opacity": 12,
            "line_gap_px": 9,
        },
        line_slots={
            "source": {
                "enabled": True,
                "fill_color": "#fff4b5",
                "stroke_color": "#513500",
            },
            "translation_1": {
                "enabled": True,
                "fill_color": "#b8f0ff",
                "stroke_color": "#00374b",
            },
            "translation_2": {
                "enabled": True,
                "fill_color": "#d3f8ff",
                "stroke_color": "#0d4258",
            },
        },
    ),
    "compact_overlay": _preset_style(
        preset="compact_overlay",
        label="Compact Overlay",
        description="Tighter spacing for overlays with limited screen space.",
        base={
            "font_family": '"Arial Narrow", "Segoe UI", sans-serif',
            "font_size_px": 24,
            "stroke_width_px": 2,
            "shadow_blur_px": 8,
            "shadow_offset_y_px": 2,
            "background_opacity": 10,
            "background_padding_x_px": 10,
            "background_padding_y_px": 3,
            "background_radius_px": 8,
            "line_spacing_em": 1.05,
            "line_gap_px": 5,
            "letter_spacing_em": 0.01,
        },
    ),
    "soft_shadow": _preset_style(
        preset="soft_shadow",
        label="Soft Shadow",
        description="Minimal stroke with softer shadow and a subtle pop effect.",
        base={
            "font_family": '"Segoe UI Semibold", "Segoe UI", sans-serif',
            "font_size_px": 31,
            "stroke_width_px": 1,
            "shadow_color": "#08111c",
            "shadow_blur_px": 18,
            "shadow_offset_x_px": 0,
            "shadow_offset_y_px": 5,
            "background_opacity": 0,
            "effect": "subtle_pop",
        },
    ),
    "jp_stream_single": _preset_style(
        preset="jp_stream_single",
        label="JP Stream Single",
        description="One-line focused Japanese-style subtitle direction with heavier outline and tighter spacing.",
        base={
            "font_family": '"Yu Gothic UI", "Yu Gothic", Meiryo, sans-serif',
            "font_size_px": 38,
            "font_weight": 800,
            "fill_color": "#fff8dd",
            "stroke_color": "#18100b",
            "stroke_width_px": 4,
            "shadow_color": "#090909",
            "shadow_blur_px": 16,
            "shadow_offset_y_px": 4,
            "background_color": "#120f12",
            "background_opacity": 28,
            "background_padding_x_px": 18,
            "background_padding_y_px": 6,
            "background_radius_px": 16,
            "line_spacing_em": 1.0,
            "letter_spacing_em": 0.015,
            "line_gap_px": 6,
        },
        recommended_max_visible_lines=1,
    ),
    "jp_dual_caption": _preset_style(
        preset="jp_dual_caption",
        label="JP Dual Caption",
        description="Two-line Japanese-inspired layout tuned for source + one translation or two translation lines.",
        base={
            "font_family": '"BIZ UDPGothic", "Yu Gothic UI", Meiryo, sans-serif',
            "font_size_px": 34,
            "font_weight": 800,
            "fill_color": "#ffffff",
            "stroke_color": "#090909",
            "stroke_width_px": 3,
            "shadow_color": "#000000",
            "shadow_blur_px": 12,
            "shadow_offset_y_px": 4,
            "background_color": "#121318",
            "background_opacity": 18,
            "background_padding_x_px": 16,
            "background_padding_y_px": 5,
            "background_radius_px": 14,
            "line_gap_px": 8,
        },
        line_slots={
            "source": {
                "enabled": True,
                "fill_color": "#ffe39c",
                "stroke_color": "#4a3210",
            },
            "translation_1": {
                "enabled": True,
                "fill_color": "#f7fbff",
                "stroke_color": "#0a1621",
                "font_size_px": 30,
            },
            "translation_2": {
                "enabled": True,
                "fill_color": "#d9f5ff",
                "stroke_color": "#10394a",
                "font_size_px": 28,
            },
        },
        recommended_max_visible_lines=2,
    ),
}


def prettify_custom_preset_name(name: str) -> str:
    return " ".join(part for part in str(name).replace("_", " ").replace("-", " ").split()).strip() or "Custom Style"


def clone_style_presets() -> dict[str, dict[str, Any]]:
    return deepcopy(_STYLE_PRESETS)


def preset_names() -> set[str]:
    return set(_STYLE_PRESETS.keys())


def merge_style_presets(custom_presets: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    catalog = clone_style_presets()
    current = custom_presets if isinstance(custom_presets, dict) else {}
    for preset_name, payload in current.items():
        if not isinstance(payload, dict):
            continue
        catalog[str(preset_name)] = {
            "preset": str(payload.get("preset") or preset_name),
            "label": str(payload.get("label") or prettify_custom_preset_name(str(preset_name))),
            "description": str(payload.get("description") or "User-created local subtitle style."),
            "built_in": False,
            "recommended_max_visible_lines": payload.get("recommended_max_visible_lines"),
            "base": deepcopy(payload.get("base", {})),
            "line_slots": _clone_slot_overrides(payload.get("line_slots")),
        }
    return catalog


def build_style_from_preset(
    preset_name: str,
    presets: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    catalog = presets if isinstance(presets, dict) and presets else _STYLE_PRESETS
    preset = catalog.get(preset_name) or catalog.get("clean_default") or next(iter(catalog.values()))
    return {
        "preset": preset["preset"],
        "label": preset["label"],
        "description": preset["description"],
        "built_in": bool(preset.get("built_in", True)),
        "recommended_max_visible_lines": preset.get("recommended_max_visible_lines"),
        "base": deepcopy(preset["base"]),
        "line_slots": _clone_slot_overrides(preset.get("line_slots")),
    }


def _clamp_int(raw: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    return max(minimum, min(maximum, value))


def _clamp_float(raw: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = float(default)
    return max(minimum, min(maximum, value))


def _normalize_color(raw: Any, default: str) -> str:
    value = str(raw or "").strip()
    return value or default


def _normalize_base_style(payload: Any) -> dict[str, Any]:
    current = payload if isinstance(payload, dict) else {}
    defaults = _BASE_STYLE_DEFAULTS
    text_align = str(current.get("text_align", defaults["text_align"])).strip().lower()
    if text_align not in {"left", "center", "right"}:
        text_align = defaults["text_align"]
    effect = str(current.get("effect", defaults["effect"])).strip().lower()
    if effect not in {"none", "fade", "subtle_pop"}:
        effect = defaults["effect"]

    return {
        "font_family": str(current.get("font_family", defaults["font_family"]) or defaults["font_family"]),
        "font_size_px": _clamp_int(current.get("font_size_px", defaults["font_size_px"]), defaults["font_size_px"], 12, 96),
        "font_weight": _clamp_int(current.get("font_weight", defaults["font_weight"]), defaults["font_weight"], 300, 900),
        "fill_color": _normalize_color(current.get("fill_color"), defaults["fill_color"]),
        "stroke_color": _normalize_color(current.get("stroke_color"), defaults["stroke_color"]),
        "stroke_width_px": round(
            _clamp_float(
                current.get("stroke_width_px", defaults["stroke_width_px"]),
                defaults["stroke_width_px"],
                0,
                8,
            ),
            2,
        ),
        "shadow_color": _normalize_color(current.get("shadow_color"), defaults["shadow_color"]),
        "shadow_blur_px": round(
            _clamp_float(
                current.get("shadow_blur_px", defaults["shadow_blur_px"]),
                defaults["shadow_blur_px"],
                0,
                32,
            ),
            2,
        ),
        "shadow_offset_x_px": round(
            _clamp_float(
                current.get("shadow_offset_x_px", defaults["shadow_offset_x_px"]),
                defaults["shadow_offset_x_px"],
                -24,
                24,
            ),
            2,
        ),
        "shadow_offset_y_px": round(
            _clamp_float(
                current.get("shadow_offset_y_px", defaults["shadow_offset_y_px"]),
                defaults["shadow_offset_y_px"],
                -24,
                24,
            ),
            2,
        ),
        "background_color": _normalize_color(current.get("background_color"), defaults["background_color"]),
        "background_opacity": _clamp_int(current.get("background_opacity", defaults["background_opacity"]), defaults["background_opacity"], 0, 100),
        "background_padding_x_px": _clamp_int(current.get("background_padding_x_px", defaults["background_padding_x_px"]), defaults["background_padding_x_px"], 0, 40),
        "background_padding_y_px": _clamp_int(current.get("background_padding_y_px", defaults["background_padding_y_px"]), defaults["background_padding_y_px"], 0, 24),
        "background_radius_px": _clamp_int(current.get("background_radius_px", defaults["background_radius_px"]), defaults["background_radius_px"], 0, 40),
        "line_spacing_em": round(_clamp_float(current.get("line_spacing_em", defaults["line_spacing_em"]), defaults["line_spacing_em"], 0.8, 2.2), 2),
        "letter_spacing_em": round(_clamp_float(current.get("letter_spacing_em", defaults["letter_spacing_em"]), defaults["letter_spacing_em"], -0.08, 0.2), 3),
        "text_align": text_align,
        "line_gap_px": _clamp_int(current.get("line_gap_px", defaults["line_gap_px"]), defaults["line_gap_px"], 0, 40),
        "effect": effect,
    }


def _normalize_override_style(payload: Any) -> dict[str, Any]:
    current = payload if isinstance(payload, dict) else {}
    normalized: dict[str, Any] = {"enabled": bool(current.get("enabled", False))}
    base = _normalize_base_style(current)
    for key in _OVERRIDE_ALLOWED_FIELDS:
        value = current.get(key)
        normalized[key] = base[key] if value not in (None, "") else None
    return normalized


def _normalize_line_slot_overrides(
    payload: Any,
    *,
    preset_style: dict[str, Any],
    legacy_source_override: Any = None,
    legacy_translation_override: Any = None,
) -> dict[str, dict[str, Any]]:
    current = payload if isinstance(payload, dict) else {}
    normalized: dict[str, dict[str, Any]] = {}
    preset_slots = preset_style.get("line_slots", {})

    for slot_name in LINE_SLOT_NAMES:
        source_payload = current.get(slot_name, preset_slots.get(slot_name, _empty_slot_override()))
        if slot_name == "source" and legacy_source_override is not None and slot_name not in current:
            source_payload = legacy_source_override
        if (
            slot_name in TRANSLATION_LINE_SLOT_NAMES
            and legacy_translation_override is not None
            and slot_name not in current
        ):
            source_payload = legacy_translation_override
        normalized[slot_name] = _normalize_override_style(source_payload)
    return normalized


def _normalize_custom_presets(payload: Any) -> dict[str, dict[str, Any]]:
    current = payload if isinstance(payload, dict) else {}
    normalized: dict[str, dict[str, Any]] = {}
    for preset_name, preset_payload in current.items():
        key = str(preset_name).strip()
        if not key:
            continue
        catalog = merge_style_presets(normalized)
        preset_style = _normalize_style_payload(
            preset_payload,
            preset_catalog=catalog,
            fallback_preset_name="clean_default",
        )
        preset_style["preset"] = key
        preset_style["label"] = str(preset_payload.get("label") or prettify_custom_preset_name(key))
        preset_style["description"] = str(
            preset_payload.get("description") or "User-created local subtitle style."
        )
        preset_style["built_in"] = False
        normalized[key] = preset_style
    return normalized


def _normalize_style_payload(
    payload: Any,
    *,
    preset_catalog: dict[str, dict[str, Any]],
    fallback_preset_name: str = "clean_default",
) -> dict[str, Any]:
    current = payload if isinstance(payload, dict) else {}
    preset_name = str(current.get("preset", fallback_preset_name)).strip()
    if preset_name not in preset_catalog:
        preset_name = fallback_preset_name
    preset_style = build_style_from_preset(preset_name, preset_catalog)

    return {
        "preset": preset_name,
        "label": str(current.get("label") or preset_style["label"]),
        "description": str(current.get("description") or preset_style["description"]),
        "built_in": bool(preset_style.get("built_in", True)),
        "recommended_max_visible_lines": current.get(
            "recommended_max_visible_lines",
            preset_style.get("recommended_max_visible_lines"),
        ),
        "base": _normalize_base_style(current.get("base", preset_style["base"])),
        "line_slots": _normalize_line_slot_overrides(
            current.get("line_slots"),
            preset_style=preset_style,
            legacy_source_override=current.get("source_override"),
            legacy_translation_override=current.get("translation_override"),
        ),
    }


def normalize_subtitle_style_config(payload: Any) -> dict[str, Any]:
    current = payload if isinstance(payload, dict) else {}
    custom_presets = _normalize_custom_presets(current.get("custom_presets"))
    preset_catalog = merge_style_presets(custom_presets)
    normalized = _normalize_style_payload(
        current,
        preset_catalog=preset_catalog,
        fallback_preset_name="clean_default",
    )
    normalized["custom_presets"] = custom_presets
    return normalized


def _merge_slot_style(base_style: dict[str, Any], override_style: dict[str, Any]) -> dict[str, Any]:
    if not override_style.get("enabled"):
        return deepcopy(base_style)
    merged = deepcopy(base_style)
    for key in _OVERRIDE_ALLOWED_FIELDS:
        value = override_style.get(key)
        if value not in (None, ""):
            merged[key] = value
    return merged


def resolve_effective_subtitle_style(payload: Any) -> dict[str, Any]:
    normalized = normalize_subtitle_style_config(payload)
    base_style = deepcopy(normalized["base"])
    resolved_line_slots = {
        slot_name: _merge_slot_style(base_style, normalized["line_slots"].get(slot_name, _empty_slot_override()))
        for slot_name in LINE_SLOT_NAMES
    }
    return {
        "preset": normalized["preset"],
        "label": normalized["label"],
        "description": normalized["description"],
        "built_in": normalized.get("built_in", True),
        "recommended_max_visible_lines": normalized.get("recommended_max_visible_lines"),
        "effect": base_style["effect"],
        "container": {
            "text_align": base_style["text_align"],
            "line_gap_px": base_style["line_gap_px"],
        },
        "base": base_style,
        "line_slots": resolved_line_slots,
        "roles": {
            "source": resolved_line_slots["source"],
            "translation": resolved_line_slots["translation_1"],
        },
    }
