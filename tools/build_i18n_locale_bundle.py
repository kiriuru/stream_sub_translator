"""Merge per-locale files into one synchronous bundle for HTML script tags."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "frontend" / "js" / "i18n" / "locales"
OUT = ROOT / "frontend" / "js" / "i18n" / "locales-bundle.js"
LOCALE_CODES = ("en", "ru", "ja", "ko", "zh")


def extract_object(locale: str, text: str) -> str:
    match = re.search(rf"window\.__SST_I18N_LOCALES\.{locale}\s*=\s*(\{{.*?\}});\s*", text, re.S)
    if not match:
        raise SystemExit(f"Could not parse locale object: {locale}")
    return match.group(1)


def main() -> None:
    lines = [
        "(function () {",
        "  window.__SST_I18N_LOCALES = window.__SST_I18N_LOCALES || {};",
    ]
    for locale in LOCALE_CODES:
        path = LOCALES_DIR / f"{locale}.js"
        text = path.read_text(encoding="utf-8")
        lines.append(f"  window.__SST_I18N_LOCALES.{locale} = {extract_object(locale, text)};")
    lines.extend(["})();", ""])
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
