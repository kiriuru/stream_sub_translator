from __future__ import annotations

import unittest

from backend.core.subtitle_style import normalize_subtitle_style_config


class SubtitleStyleEffectsTests(unittest.TestCase):
    def test_normalize_preserves_extended_web_effects(self) -> None:
        for effect in ("slide_up", "zoom_in", "blur_in", "glow", "fade", "subtle_pop", "none"):
            with self.subTest(effect=effect):
                payload = {
                    "preset": "clean_default",
                    "base": {"effect": effect},
                }
                normalized = normalize_subtitle_style_config(payload)
                self.assertEqual(normalized["base"]["effect"], effect)

    def test_normalize_rejects_unknown_effect_to_default(self) -> None:
        payload = {
            "preset": "clean_default",
            "base": {"effect": "spin_wildly"},
        }
        normalized = normalize_subtitle_style_config(payload)
        self.assertEqual(normalized["base"]["effect"], "none")


if __name__ == "__main__":
    unittest.main()
