from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from urllib.parse import quote


_FONT_EXTENSIONS: dict[str, str] = {
    ".ttf": "truetype",
    ".otf": "opentype",
    ".woff": "woff",
    ".woff2": "woff2",
}

_FALLBACK_FONT_CATALOG: list[dict[str, str]] = [
    {
        "id": "fallback-segoe-ui",
        "label": "Segoe UI",
        "family": '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
        "source": "fallback",
    },
    {
        "id": "fallback-yu-gothic-ui",
        "label": "Yu Gothic UI",
        "family": '"Yu Gothic UI", "Yu Gothic", Meiryo, sans-serif',
        "source": "fallback",
    },
    {
        "id": "fallback-biz-udpgothic",
        "label": "BIZ UDPGothic",
        "family": '"BIZ UDPGothic", "Yu Gothic UI", Meiryo, sans-serif',
        "source": "fallback",
    },
    {
        "id": "fallback-meiryo",
        "label": "Meiryo",
        "family": '"Meiryo", "Yu Gothic UI", sans-serif',
        "source": "fallback",
    },
    {
        "id": "fallback-arial",
        "label": "Arial",
        "family": 'Arial, "Segoe UI", sans-serif',
        "source": "fallback",
    },
    {
        "id": "fallback-verdana",
        "label": "Verdana",
        "family": 'Verdana, "Segoe UI", sans-serif',
        "source": "fallback",
    },
    {
        "id": "fallback-trebuchet",
        "label": "Trebuchet MS",
        "family": '"Trebuchet MS", "Segoe UI", sans-serif',
        "source": "fallback",
    },
    {
        "id": "fallback-ud-digi",
        "label": "UD Digi Kyokasho",
        "family": '"UD Digi Kyokasho NK-R", "Yu Gothic UI", Meiryo, sans-serif',
        "source": "fallback",
    },
]


def _project_font_family_name(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(stem.split()) or path.stem


def list_project_font_entries(project_fonts_dir: Path) -> list[dict[str, str]]:
    project_fonts_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []
    for path in sorted(project_fonts_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in _FONT_EXTENSIONS:
            continue
        family_name = _project_font_family_name(path)
        entries.append(
            {
                "id": f"project-{path.stem.lower()}",
                "label": family_name,
                "family": f'"{family_name}"',
                "source": "project_local",
                "url": f"/project-fonts/{quote(path.name)}",
                "filename": path.name,
                "format": _FONT_EXTENSIONS[suffix],
            }
        )
    return entries


def build_font_catalog(project_fonts_dir: Path) -> dict[str, object]:
    return {
        "project_fonts_dir": str(project_fonts_dir),
        "project_local": list_project_font_entries(project_fonts_dir),
        "fallback": deepcopy(_FALLBACK_FONT_CATALOG),
    }


def build_project_fonts_stylesheet(project_fonts_dir: Path) -> str:
    rules: list[str] = []
    for entry in list_project_font_entries(project_fonts_dir):
        url = entry["url"]
        family = entry["label"].replace('"', '\\"')
        fmt = entry["format"]
        rules.append(
            "\n".join(
                [
                    "@font-face {",
                    f'  font-family: "{family}";',
                    f'  src: url("{url}") format("{fmt}");',
                    "  font-display: swap;",
                    "}",
                ]
            )
        )
    if not rules:
        return "/* No project-local fonts found in the fonts folder yet. */\n"
    return "\n\n".join(rules) + "\n"
