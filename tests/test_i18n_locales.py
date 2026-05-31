from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
I18N_JS = PROJECT_ROOT / "frontend" / "js" / "i18n.js"
LOCALES_DIR = PROJECT_ROOT / "frontend" / "js" / "i18n" / "locales"
INDEX_HTML = PROJECT_ROOT / "frontend" / "index.html"
ALL_LOCALES = ("en", "ru", "ja", "ko", "zh")


def _load_locale(locale: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{locale}.js"
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.__SST_I18N_LOCALES\.{locale}\s*=\s*(\{{.*\}});", text, re.S)
    if not match:
        raise AssertionError(f"Could not parse locale bundle: {locale}")
    return json.loads(match.group(1))


class I18nLocaleSupportTests(unittest.TestCase):
    def test_i18n_core_builds_from_preloaded_bundles(self) -> None:
        source = I18N_JS.read_text(encoding="utf-8")
        for code in ALL_LOCALES:
            self.assertIn(f'"{code}"', source)
        self.assertIn("getCatalog", source)
        self.assertIn("__SST_I18N_LOCALES", source)
        self.assertIn("locales-bundle.js", INDEX_HTML.read_text(encoding="utf-8"))
        self.assertNotIn("fetch(", source)
        self.assertNotIn("mergeExternalLocale", source)

    def test_locale_bundles_exist_and_cover_core_keys(self) -> None:
        en_keys = set(_load_locale("en"))
        ru_keys = set(_load_locale("ru"))
        self.assertEqual(en_keys, ru_keys)
        for locale in ("ja", "ko", "zh"):
            payload = _load_locale(locale)
            self.assertIn("header.title", payload)
            self.assertIn(f"language.{locale}", payload)
            self.assertIn("tools.source_replacement.builtin", payload)
            for code in ALL_LOCALES:
                self.assertIn(f"language.{code}", payload, msg=f"{locale} language.{code}")

    def test_index_eager_loads_locale_bundle_before_i18n(self) -> None:
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("/static/js/i18n/locales-bundle.js", html)
        self.assertIn("/static/js/i18n/dynamic-locales.js", html)
        bundle_pos = html.index("/static/js/i18n/locales-bundle.js")
        dynamic_pos = html.index("/static/js/i18n/dynamic-locales.js")
        i18n_pos = html.index("/static/js/i18n.js")
        self.assertLess(bundle_pos, dynamic_pos)
        self.assertLess(dynamic_pos, i18n_pos)
        bundle_path = PROJECT_ROOT / "frontend" / "js" / "i18n" / "locales-bundle.js"
        self.assertTrue(bundle_path.is_file(), msg=str(bundle_path))

    def test_index_language_select_includes_all_locales(self) -> None:
        html = INDEX_HTML.read_text(encoding="utf-8")
        for locale in ALL_LOCALES:
            self.assertIn(f'value="{locale}"', html)


if __name__ == "__main__":
    unittest.main()
