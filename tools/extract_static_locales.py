"""Read or refresh en/ru locale bundles under frontend/js/i18n/locales/.

Static strings live in locales/en.js and locales/ru.js (loaded eagerly in HTML).
i18n.js only merges preloaded bundles at init — edit the locale files directly.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "frontend" / "js" / "i18n" / "locales"


def load_locale(locale: str) -> dict[str, str]:
    path = OUT_DIR / f"{locale}.js"
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.__SST_I18N_LOCALES\.{locale}\s*=\s*(\{{.*\}});", text, re.S)
    if not match:
        raise SystemExit(f"Could not parse locale bundle: {path}")
    return json.loads(match.group(1))


def write_locale(locale: str, mapping: dict[str, str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{locale}.js"
    body = json.dumps(mapping, ensure_ascii=False, indent=2)
    path.write_text(
        "\n".join(
            [
                "(function () {",
                "  window.__SST_I18N_LOCALES = window.__SST_I18N_LOCALES || {};",
                f"  window.__SST_I18N_LOCALES.{locale} = {body};",
                "})();",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"wrote {path} ({len(mapping)} keys)")


def main() -> None:
    en = load_locale("en")
    ru = load_locale("ru")
    missing_ru = set(en) - set(ru)
    missing_en = set(ru) - set(en)
    if missing_ru or missing_en:
        print(f"en keys: {len(en)}, ru keys: {len(ru)}")
        if missing_ru:
            print(f"  missing in ru: {sorted(missing_ru)[:12]}")
        if missing_en:
            print(f"  missing in en: {sorted(missing_en)[:12]}")
        raise SystemExit(1)
    print(f"en/ru parity OK ({len(en)} keys each)")


if __name__ == "__main__":
    main()
