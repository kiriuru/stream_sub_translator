from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
I18N_JS = PROJECT_ROOT / "frontend" / "js" / "i18n.js"
DYNAMIC_JS = PROJECT_ROOT / "frontend" / "js" / "i18n" / "dynamic-locales.js"
LOCALES_DIR = PROJECT_ROOT / "frontend" / "js" / "i18n" / "locales"
EN_JS = LOCALES_DIR / "en.js"


def _load_locale(locale: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{locale}.js"
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.__SST_I18N_LOCALES\.{locale}\s*=\s*(\{{.*\}});", text, re.S)
    return json.loads(match.group(1))


def _extract_en_catalog() -> dict[str, str]:
    catalog = dict(_load_locale("en"))
    dynamic = re.search(r"\ben:\s*(\{.*?\})\s*,\s*\n\s*ru:\s*\{", DYNAMIC_JS.read_text(encoding="utf-8"), re.S)
    catalog.update(json.loads(dynamic.group(1)))
    return catalog


def _extract_en_keys() -> set[str]:
    return set(_extract_en_catalog())


def _has_target_script(locale: str, text: str) -> bool:
    if locale == "ja":
        return bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text))
    if locale == "ko":
        return bool(re.search(r"[\uac00-\ud7af]", text))
    if locale == "zh":
        return bool(re.search(r"[\u4e00-\u9fff]", text))
    return True


class I18nDynamicLocaleTests(unittest.TestCase):
    def test_dynamic_locales_file_exists(self) -> None:
        self.assertTrue(DYNAMIC_JS.is_file())
        self.assertTrue(EN_JS.is_file())

    def test_cjk_locale_files_cover_full_english_catalog(self) -> None:
        en_keys = _extract_en_keys()
        for locale in ("ja", "ko", "zh"):
            payload = _load_locale(locale)
            missing = en_keys - set(payload)
            self.assertEqual(missing, set(), msg=f"{locale} missing: {sorted(missing)[:8]}")

    def test_cjk_user_facing_strings_use_target_script(self) -> None:
        for locale in ("ja", "ko", "zh"):
            payload = _load_locale(locale)
            for key in (
                "overlay.preset_hint.single",
                "overlay.preset_hint.dual_line",
                "overlay.preset_hint.stacked",
                "translation.result.empty",
                "style.field.outline_color",
            ):
                self.assertIn(key, payload, msg=f"{locale} missing {key}")
                self.assertTrue(
                    _has_target_script(locale, payload[key]),
                    msg=f"{locale} {key} not localized: {payload[key]!r}",
                )

    def test_language_selector_labels_present_in_cjk(self) -> None:
        for locale in ("ja", "ko", "zh"):
            payload = _load_locale(locale)
            for code in ("en", "ru", "ja", "ko", "zh"):
                self.assertIn(f"language.{code}", payload, msg=f"{locale} language.{code}")

    def test_dynamic_keys_merged_at_build_time(self) -> None:
        source = I18N_JS.read_text(encoding="utf-8")
        self.assertIn("__SST_I18N_DYNAMIC", source)
        self.assertIn("getCatalog", source)
        sample = "diagnostics.local_parakeet.line"
        self.assertIn(sample, _extract_en_keys())


class UiLanguageAutoTests(unittest.TestCase):
    def test_frontend_normalize_empty_language(self) -> None:
        path = PROJECT_ROOT / "frontend" / "js" / "normalizers" / "config-normalizer.js"
        source = path.read_text(encoding="utf-8")
        self.assertIn('return ""', source)
        self.assertIn('current.startsWith("ru")', source)


if __name__ == "__main__":
    unittest.main()
