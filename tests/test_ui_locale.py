from __future__ import annotations

import unittest

from desktop.launcher_context import _SPLASH_I18N
from desktop.ui_locale import normalize_ui_language


class UiLocaleTests(unittest.TestCase):
    def test_normalize_accepts_cjk_locales(self) -> None:
        self.assertEqual(normalize_ui_language("ja"), "ja")
        self.assertEqual(normalize_ui_language("ko"), "ko")
        self.assertEqual(normalize_ui_language("zh"), "zh")
        self.assertEqual(normalize_ui_language("zh-CN"), "zh")
        self.assertEqual(normalize_ui_language("ja-JP"), "ja")
        self.assertEqual(normalize_ui_language("unknown"), "en")

    def test_normalize_ru_bcp47_tag(self) -> None:
        self.assertEqual(normalize_ui_language("ru-RU"), "ru")
        self.assertEqual(normalize_ui_language("en-US"), "en")

    def test_splash_cjk_catalogs_cover_en_keys(self) -> None:
        en_keys = set(_SPLASH_I18N["en"])
        for locale in ("ja", "ko", "zh"):
            catalog = _SPLASH_I18N[locale]
            self.assertEqual(en_keys, set(catalog.keys()), msg=locale)


if __name__ == "__main__":
    unittest.main()
