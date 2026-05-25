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

SUBTITLE_EFFECT_IDS: frozenset[str] = frozenset(
    {"none", "fade", "subtle_pop", "slide_up", "zoom_in", "blur_in", "glow"}
)

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


# Visually-distinct preset catalog. Each entry pairs a clearly different
# bundled font with a clearly different palette / background / effect so the
# user can scan the gallery and pick a recognisable look. Themed presets
# (Anime Stream, Retro Terminal, Fallout Pip-Boy, Cyberpunk Neon, Film Noir,
# Comic Burst) use dedicated fonts downloaded by `scripts/download_bundled_fonts.py`
# — bundled font family names match the @font-face declarations emitted by
# `build_project_fonts_stylesheet` for files in `<repo>/fonts/`.
#
# Background opacity rule: any preset that uses a plate must run >=88% so the
# subtitle stays readable on dashboards / overlays with dark page backgrounds
# (a 50–60% plate on a dark dashboard preview looked like "dark text on dark
# background" in the v0.4.2 reviews).
_STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "clean_default": _preset_style(
        preset="clean_default",
        label="Clean Default",
        description="Neutral baseline: Inter on a transparent background with a minimal black outline.",
        base={
            "font_family": '"Inter Regular", "Segoe UI", Tahoma, sans-serif',
            "font_size_px": 30,
            "font_weight": 500,
            "fill_color": "#ffffff",
            "stroke_color": "#1c1f25",
            "stroke_width_px": 1.5,
            "shadow_color": "#000000",
            "shadow_blur_px": 8,
            "shadow_offset_y_px": 2,
            "background_opacity": 0,
            "line_gap_px": 8,
            "letter_spacing_em": 0,
            "effect": "none",
        },
    ),
    "streamer_bold": _preset_style(
        preset="streamer_bold",
        label="Streamer Neon",
        description="Loud display look: Oswald with a cyan fill and a hot-magenta glow for live gameplay.",
        base={
            "font_family": '"Oswald Bold", "Impact", "Arial Narrow Bold", sans-serif',
            "font_size_px": 38,
            "font_weight": 800,
            "fill_color": "#00f0ff",
            "stroke_color": "#0a0612",
            "stroke_width_px": 3.5,
            "shadow_color": "#ff2bd6",
            "shadow_blur_px": 24,
            "shadow_offset_x_px": 0,
            "shadow_offset_y_px": 0,
            "background_opacity": 0,
            "letter_spacing_em": 0.02,
            "line_gap_px": 10,
            "effect": "glow",
        },
    ),
    "dual_tone": _preset_style(
        preset="dual_tone",
        label="Dual Color",
        description="Lato body with distinct fill colors per slot so source and each translation read at a glance.",
        base={
            "font_family": '"Lato Regular", "Verdana", "Segoe UI", sans-serif',
            "font_size_px": 30,
            "font_weight": 700,
            "fill_color": "#ffffff",
            "stroke_color": "#13151a",
            "stroke_width_px": 2,
            "shadow_color": "#000000",
            "shadow_blur_px": 6,
            "shadow_offset_y_px": 2,
            "background_opacity": 0,
            "line_gap_px": 8,
            "effect": "fade",
        },
        line_slots={
            "source": {
                "enabled": True,
                "fill_color": "#ffd60a",
                "stroke_color": "#4a3000",
            },
            "translation_1": {
                "enabled": True,
                "fill_color": "#7be2ff",
                "stroke_color": "#0b2c3a",
            },
            "translation_2": {
                "enabled": True,
                "fill_color": "#a8ffb8",
                "stroke_color": "#0b3a18",
            },
            "translation_3": {
                "enabled": True,
                "fill_color": "#ff9fc5",
                "stroke_color": "#3a0b22",
            },
        },
    ),
    "compact_overlay": _preset_style(
        preset="compact_overlay",
        label="Compact Bar",
        description="Source Sans 3 inside a tight semi-opaque black bar — small footprint, maximum legibility.",
        base={
            "font_family": '"Source Sans 3 Regular", "Source Sans 3 Bold", "Segoe UI", sans-serif',
            "font_size_px": 22,
            "font_weight": 600,
            "fill_color": "#ffffff",
            "stroke_color": "#000000",
            "stroke_width_px": 0,
            "shadow_color": "#000000",
            "shadow_blur_px": 0,
            "shadow_offset_y_px": 0,
            "background_color": "#0a0d12",
            "background_opacity": 90,
            "background_padding_x_px": 14,
            "background_padding_y_px": 4,
            "background_radius_px": 4,
            "line_spacing_em": 1.05,
            "line_gap_px": 4,
            "letter_spacing_em": 0,
            "effect": "none",
        },
        recommended_max_visible_lines=2,
    ),
    "soft_shadow": _preset_style(
        preset="soft_shadow",
        label="Soft Cloud",
        description="Comfortaa with a wide diffused shadow and zero outline — feels airy, no edge crunch.",
        base={
            "font_family": '"Comfortaa Regular", "Segoe UI", sans-serif',
            "font_size_px": 30,
            "font_weight": 500,
            "fill_color": "#fff8eb",
            "stroke_color": "#3a2a18",
            "stroke_width_px": 0,
            "shadow_color": "#1d1410",
            "shadow_blur_px": 22,
            "shadow_offset_x_px": 0,
            "shadow_offset_y_px": 6,
            "background_opacity": 0,
            "line_gap_px": 9,
            "letter_spacing_em": 0.01,
            "effect": "subtle_pop",
        },
    ),
    # Reworked: real anime/VTuber caption look using Mochiy Pop One — a bold
    # Classic fansub-style anime caption: pure white rounded display face,
    # crisp dark-violet outline (medium thickness — heavy strokes turned the
    # text into a black blob in the v0.4.2 attempt), and a soft dark drop
    # shadow for separation from busy stream backgrounds. Mochiy Pop One
    # handles Latin/Japanese, Comfortaa-Bold carries Cyrillic without
    # falling back to a serif. No coloured glow — coloured glows are what
    # made the previous version read as a goth poster on user backgrounds.
    "anime_stream": _preset_style(
        preset="anime_stream",
        label="Anime Stream",
        description="Mochiy Pop One for Latin/Japanese + Comfortaa Bold for Cyrillic — classic anime fansub caption: white fill, crisp violet outline, soft dark drop shadow.",
        base={
            "font_family": '"Mochiy Pop One Regular", "Comfortaa Bold", "Underdog Regular", "Bangers Regular", "Comic Relief Bold", "Poppins Bold", "Segoe UI", sans-serif',
            "font_size_px": 40,
            "font_weight": 800,
            "fill_color": "#ffffff",
            "stroke_color": "#3a1a5c",
            "stroke_width_px": 1,
            "shadow_color": "#15071f",
            "shadow_blur_px": 8,
            "shadow_offset_x_px": 0,
            "shadow_offset_y_px": 3,
            "background_opacity": 0,
            "line_spacing_em": 1.1,
            "letter_spacing_em": 0.015,
            "line_gap_px": 6,
            "effect": "subtle_pop",
        },
        recommended_max_visible_lines=2,
    ),
    # Reworked: was unreadable on the dark dashboard preview (yellow at 88%
    # opacity over near-black on a near-black page looked like "black on
    # black"). Now: pure white text on a solid pure-black plate at 100%
    # opacity — WCAG AAA contrast, recognisable from any page background.
    "accessibility_high_contrast": _preset_style(
        preset="accessibility_high_contrast",
        label="Max Contrast",
        description="Pure white Montserrat Bold on a solid 100%-opaque black plate — WCAG AAA contrast in any environment.",
        base={
            "font_family": '"Montserrat Bold", "Montserrat Regular", "Segoe UI", sans-serif',
            "font_size_px": 36,
            "font_weight": 800,
            "fill_color": "#ffffff",
            "stroke_color": "#000000",
            "stroke_width_px": 0,
            "shadow_color": "#000000",
            "shadow_blur_px": 0,
            "shadow_offset_y_px": 0,
            "background_color": "#000000",
            "background_opacity": 100,
            "background_padding_x_px": 24,
            "background_padding_y_px": 10,
            "background_radius_px": 6,
            "line_spacing_em": 1.2,
            "letter_spacing_em": 0.02,
            "line_gap_px": 8,
            "effect": "none",
        },
        recommended_max_visible_lines=2,
    ),
    # Reworked: was barely visible on dark dashboard backgrounds because the
    # plate ran at 58% opacity over near-black. Now: ivory Playfair Display
    # Bold on a warm sepia plate at 95% opacity — a proper "art-house"
    # letterboxed look that pops on both light and dark page backgrounds.
    "dark_cinema": _preset_style(
        preset="dark_cinema",
        label="Cinema Plate",
        description="Playfair Display ivory on a solid warm sepia plate — letterboxed art-house aesthetic, readable on any background.",
        base={
            "font_family": '"Playfair Display Bold", "Playfair Display Regular", Georgia, "Times New Roman", serif',
            "font_size_px": 30,
            "font_weight": 700,
            "fill_color": "#f4e3b8",
            "stroke_color": "#1a0a05",
            "stroke_width_px": 0,
            "shadow_color": "#08040a",
            "shadow_blur_px": 6,
            "shadow_offset_y_px": 2,
            "background_color": "#1a0d08",
            "background_opacity": 95,
            "background_padding_x_px": 26,
            "background_padding_y_px": 10,
            "background_radius_px": 4,
            "line_spacing_em": 1.18,
            "letter_spacing_em": 0.02,
            "line_gap_px": 8,
            "effect": "fade",
        },
        line_slots={
            "translation_1": {
                "enabled": True,
                "fill_color": "#e8d4a0",
                "stroke_color": "#08040a",
                "font_size_px": 24,
            },
        },
        recommended_max_visible_lines=2,
    ),
    "meeting_soft": _preset_style(
        preset="meeting_soft",
        label="Podcast Subtle",
        description="Roboto Regular in light grey with no stroke and no plate — minimal, talking-head friendly.",
        base={
            "font_family": '"Roboto Regular", "Segoe UI", "Calibri", sans-serif',
            "font_size_px": 24,
            "font_weight": 400,
            "fill_color": "#e8edf5",
            "stroke_color": "#000000",
            "stroke_width_px": 0,
            "shadow_color": "#0b1018",
            "shadow_blur_px": 8,
            "shadow_offset_y_px": 1,
            "background_opacity": 0,
            "line_spacing_em": 1.18,
            "letter_spacing_em": 0,
            "line_gap_px": 5,
            "effect": "none",
        },
        recommended_max_visible_lines=3,
    ),
    # Reworked: was just "JetBrains Mono in CRT green" with a JetBrains shape
    # — that reads as code editor, not retro. Replaced with VT323 (an actual
    # DEC VT320 phosphor emulation) in classic amber on a dark CRT plate,
    # plus letter-spacing and a generous glow for that "warm terminal at
    # 2 AM" look.
    "retro_terminal": _preset_style(
        preset="retro_terminal",
        label="Retro Terminal",
        description="VT323 amber phosphor on a dark CRT panel — DEC VT320 / Apple ][ vibe with PT Mono for Cyrillic.",
        base={
            "font_family": '"VT323 Regular", "PT Mono Regular", "Share Tech Mono Regular", "Consolas", "Courier New", monospace',
            "font_size_px": 36,
            "font_weight": 400,
            "fill_color": "#ffb000",
            "stroke_color": "#3a1c00",
            "stroke_width_px": 0,
            "shadow_color": "#ff8800",
            "shadow_blur_px": 14,
            "shadow_offset_x_px": 0,
            "shadow_offset_y_px": 0,
            "background_color": "#0a0805",
            "background_opacity": 92,
            "background_padding_x_px": 18,
            "background_padding_y_px": 6,
            "background_radius_px": 2,
            "line_spacing_em": 1.05,
            "letter_spacing_em": 0.04,
            "line_gap_px": 4,
            "effect": "glow",
        },
        recommended_max_visible_lines=3,
    ),
    # NEW: Pip-Boy / Fallout aesthetic — distinctly green CRT, more saturated
    # and slimmer than retro_terminal. Uses Share Tech Mono (sharper square
    # grid than VT323, closer to the proprietary Monofonto used in-game) plus
    # the canonical Pip-Boy phosphor green and a strong soft glow.
    "fallout_pipboy": _preset_style(
        preset="fallout_pipboy",
        label="Fallout Pip-Boy",
        description="Share Tech Mono in Pip-Boy phosphor green with a strong scanline glow; Ubuntu Mono Bold covers Cyrillic.",
        base={
            "font_family": '"Share Tech Mono Regular", "Ubuntu Mono Bold", "Ubuntu Mono Regular", "PT Mono Regular", "VT323 Regular", "Consolas", "Courier New", monospace',
            "font_size_px": 30,
            "font_weight": 400,
            "fill_color": "#4cff79",
            "stroke_color": "#001f0a",
            "stroke_width_px": 0,
            "shadow_color": "#16ff3c",
            "shadow_blur_px": 18,
            "shadow_offset_x_px": 0,
            "shadow_offset_y_px": 0,
            "background_color": "#020806",
            "background_opacity": 95,
            "background_padding_x_px": 18,
            "background_padding_y_px": 6,
            "background_radius_px": 2,
            "line_spacing_em": 1.08,
            "letter_spacing_em": 0.05,
            "line_gap_px": 5,
            "effect": "glow",
        },
        recommended_max_visible_lines=3,
    ),
    # Reworked: was Bebas Neue in magenta — that reads as "loud streamer",
    # not "comic". Now uses Bangers, the standard Google Fonts comic-action
    # display, with the classic yellow-fill / black-stroke / red-shadow combo
    # straight out of a Marvel onomatopoeia panel.
    "comic_burst": _preset_style(
        preset="comic_burst",
        label="Comic Burst",
        description="Bangers in comic-yellow with a chunky black outline and a hot-red shadow — Marvel SFX panel energy; Comic Relief Bold covers Cyrillic.",
        base={
            "font_family": '"Bangers Regular", "Comic Relief Bold", "Comic Relief Regular", "Impact", "Arial Black", sans-serif',
            "font_size_px": 46,
            "font_weight": 400,
            "fill_color": "#ffd60a",
            "stroke_color": "#0a0a0a",
            "stroke_width_px": 5,
            "shadow_color": "#d6172a",
            "shadow_blur_px": 4,
            "shadow_offset_x_px": 4,
            "shadow_offset_y_px": 6,
            "background_opacity": 0,
            "letter_spacing_em": 0.045,
            "line_gap_px": 8,
            "effect": "zoom_in",
        },
        recommended_max_visible_lines=1,
    ),
    # NEW: Cyberpunk neon — Orbitron Black is THE geometric-display sci-fi
    # font, magenta fill + cyan glow on a deep blue-black plate produces the
    # classic 2077 / synthwave look without going off-brand into vapor wave.
    "cyberpunk_neon": _preset_style(
        preset="cyberpunk_neon",
        label="Cyberpunk Neon",
        description="Orbitron Black in hot magenta with a cyan halo glow on a deep navy plate; Exo 2 Black handles Cyrillic with the same sci-fi geometry.",
        base={
            "font_family": '"Orbitron Black", "Exo 2 Black", "Orbitron Regular", "Exo 2 Regular", "Audiowide", sans-serif',
            "font_size_px": 32,
            "font_weight": 900,
            "fill_color": "#ff2bd6",
            "stroke_color": "#03001a",
            "stroke_width_px": 2,
            "shadow_color": "#00f0ff",
            "shadow_blur_px": 22,
            "shadow_offset_x_px": 0,
            "shadow_offset_y_px": 0,
            "background_color": "#070416",
            "background_opacity": 88,
            "background_padding_x_px": 20,
            "background_padding_y_px": 8,
            "background_radius_px": 4,
            "line_spacing_em": 1.15,
            "letter_spacing_em": 0.06,
            "line_gap_px": 7,
            "effect": "glow",
        },
        recommended_max_visible_lines=2,
    ),
    # NEW: Film Noir — Special Elite mimics a worn IBM Selectric. Sepia
    # parchment on a near-black plate with low contrast for that 40s detective
    # / typewritten dossier feel; no flashy effect, just a calm fade.
    "noir_typewriter": _preset_style(
        preset="noir_typewriter",
        label="Film Noir",
        description="Special Elite typewriter on a deep ink plate — 1940s detective / typewritten dossier mood; Cutive Mono carries the same vibe for Cyrillic.",
        base={
            "font_family": '"Special Elite Regular", "Cutive Mono Regular", "PT Mono Regular", "Courier New", "Consolas", monospace',
            "font_size_px": 28,
            "font_weight": 400,
            "fill_color": "#ece1c4",
            "stroke_color": "#1a1208",
            "stroke_width_px": 0,
            "shadow_color": "#000000",
            "shadow_blur_px": 4,
            "shadow_offset_x_px": 0,
            "shadow_offset_y_px": 2,
            "background_color": "#100a06",
            "background_opacity": 92,
            "background_padding_x_px": 22,
            "background_padding_y_px": 10,
            "background_radius_px": 0,
            "line_spacing_em": 1.18,
            "letter_spacing_em": 0.03,
            "line_gap_px": 6,
            "effect": "fade",
        },
        recommended_max_visible_lines=2,
    ),
    "vlog_pastel": _preset_style(
        preset="vlog_pastel",
        label="Vlog Pastel",
        description="Poppins on a warm pastel pill — cozy lifestyle / vlog look, plays nicely with soft backgrounds.",
        base={
            "font_family": '"Poppins Regular", "Poppins Bold", "Segoe UI", sans-serif',
            "font_size_px": 28,
            "font_weight": 600,
            "fill_color": "#3a1e3d",
            "stroke_color": "#3a1e3d",
            "stroke_width_px": 0,
            "shadow_color": "#a37fc3",
            "shadow_blur_px": 14,
            "shadow_offset_y_px": 3,
            "background_color": "#ffdce5",
            "background_opacity": 90,
            "background_padding_x_px": 18,
            "background_padding_y_px": 7,
            "background_radius_px": 22,
            "line_spacing_em": 1.15,
            "line_gap_px": 6,
            "effect": "slide_up",
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
    if effect not in SUBTITLE_EFFECT_IDS:
        effect = str(defaults["effect"])

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


# Legacy preset names removed in the 0.4.3 catalog rework. Mapping points the
# saved configs at the closest visual replacement so users don't get bumped
# back to `clean_default` on first launch after upgrade. Custom presets that
# happen to share these keys are still respected (they enter the catalog
# before this migration runs).
_LEGACY_PRESET_MIGRATIONS: dict[str, str] = {
    "jp_stream_single": "anime_stream",
    "jp_dual_caption": "anime_stream",
}


def _normalize_style_payload(
    payload: Any,
    *,
    preset_catalog: dict[str, dict[str, Any]],
    fallback_preset_name: str = "clean_default",
) -> dict[str, Any]:
    current = payload if isinstance(payload, dict) else {}
    preset_name = str(current.get("preset", fallback_preset_name)).strip()
    if preset_name not in preset_catalog:
        migrated = _LEGACY_PRESET_MIGRATIONS.get(preset_name)
        if migrated and migrated in preset_catalog:
            preset_name = migrated
        else:
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
