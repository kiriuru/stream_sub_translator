from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = PROJECT_ROOT / "frontend" / "index.html"
FIELD_HELP_JS = PROJECT_ROOT / "frontend" / "js" / "ui" / "field-help-popover.js"
LOCALES_DIR = PROJECT_ROOT / "frontend" / "js" / "i18n" / "locales"


def _load_locale(locale: str) -> dict[str, str]:
    text = (LOCALES_DIR / f"{locale}.js").read_text(encoding="utf-8")
    match = re.search(rf"window\.__SST_I18N_LOCALES\.{locale}\s*=\s*(\{{.*\}});", text, re.S)
    assert match
    import json

    return json.loads(match.group(1))


class FieldHelpPopoverTests(unittest.TestCase):
    def test_asr_advanced_fields_have_help_buttons_and_i18n_keys(self) -> None:
        html = INDEX_HTML.read_text(encoding="utf-8")
        panel_start = html.index('data-tab-panel="asr_advanced"')
        panel_end = html.index('data-tab-panel="tools"', panel_start)
        panel_html = html[panel_start:panel_end]

        help_keys = re.findall(r'data-field-help-key="([^"]+)"', panel_html)
        self.assertGreaterEqual(len(help_keys), 18)
        self.assertEqual(len(help_keys), len(set(help_keys)))

        en = _load_locale("en")
        ru = _load_locale("ru")
        for key in help_keys:
            self.assertIn(key, en)
            self.assertIn(key, ru)
            self.assertTrue(en[key].strip(), msg=key)
            self.assertTrue(ru[key].strip(), msg=key)

    def test_asr_advanced_notes_use_recommended_format(self) -> None:
        ru = _load_locale("ru")
        self.assertEqual(ru["tools.advanced.vad_mode.note"], "Рекомендуемое: 2")
        self.assertEqual(ru["tools.advanced.min_speech.note"], "Рекомендуемое: 180-220")
        self.assertNotIn("безопаснее", ru["tools.advanced.vad_mode.note"])

        for locale, prefix in (("ja", "推奨:"), ("ko", "권장:"), ("zh", "推荐:")):
            payload = _load_locale(locale)
            self.assertTrue(payload["tools.advanced.vad_mode.note"].startswith(prefix), locale)
            self.assertNotIn("Recommended:", payload["tools.advanced.vad_mode.note"])

    def test_asr_advanced_help_localized_for_all_locales(self) -> None:
        help_keys = [
            key
            for key in _load_locale("en")
            if key.startswith("tools.advanced.") and key.endswith(".help")
        ]
        for locale in ("ja", "ko", "zh"):
            payload = _load_locale(locale)
            for key in help_keys:
                self.assertIn(key, payload, msg=f"{locale} missing {key}")
                self.assertTrue(payload[key].strip(), msg=f"{locale} empty {key}")
                self.assertNotRegex(
                    payload[key],
                    r"^(When enabled|Applies a ready-made|Controls how partial|Voice Activity Detection)",
                    msg=f"{locale} {key} still English",
                )
            self.assertNotEqual(payload["tools.advanced.field_help.aria"], "Show setting help")

    def test_latency_preset_help_uses_localized_preset_names(self) -> None:
        cases = {
            "ja": ("超低遅延", "バランスの取れた", "balanced"),
            "ko": ("매우 낮은 대기 시간", "균형 잡힌", "balanced"),
            "zh": ("超低延迟", "均衡", "balanced"),
            "ru": ("Минимальная задержка", "Баланс", "ultra low latency"),
        }
        for locale, (ultra, balanced, forbidden) in cases.items():
            payload = _load_locale(locale)
            help_text = payload["tools.advanced.latency_preset.help"]
            note = payload["tools.advanced.latency_preset.note"]
            self.assertIn(ultra, help_text, locale)
            self.assertIn(balanced, help_text, locale)
            self.assertIn(balanced, note, locale)
            self.assertNotIn(forbidden, help_text, locale)

    def test_asr_advanced_layout_two_columns_without_side_notes(self) -> None:
        html = INDEX_HTML.read_text(encoding="utf-8")
        panel_start = html.index('data-tab-panel="asr_advanced"')
        panel_end = html.index('data-tab-panel="tools"', panel_start)
        panel_html = html[panel_start:panel_end]

        self.assertIn('class="asr-advanced-fields-grid"', panel_html)
        self.assertNotIn("asr-advanced-notes", panel_html)
        self.assertNotIn('data-i18n="tools.notes.', panel_html)

        en = _load_locale("en")
        for key in (
            "tools.notes.title",
            "tools.notes.1",
            "tools.notes.2",
            "tools.notes.3",
            "tools.notes.4",
            "tools.notes.vad",
        ):
            self.assertNotIn(key, en)

    def test_field_help_styles_use_theme_tokens(self) -> None:
        css = (PROJECT_ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
        self.assertIn(".field-help-popover", css)
        self.assertIn("background: var(--bg-panel-elevated);", css)
        self.assertNotIn("button:not(.field-help-btn)", css)
        self.assertNotIn("--surface-panel", css)
        self.assertNotIn("--surface-elevated", css)
        self.assertNotIn("--border-subtle", css)

    def test_field_help_button_not_stretched_by_global_button_rules(self) -> None:
        css = (PROJECT_ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
        help_idx = css.index("button.field-help-btn {")
        generic_width_idx = css.index("button,\n.sst-button,\ninput:not([type=\"checkbox\"])")
        self.assertGreater(help_idx, generic_width_idx)
        self.assertIn("width: 18px;", css)
        self.assertIn("min-height: 18px;", css)
        self.assertNotIn("button:not(.field-help-btn)", css)
        self.assertIn("flex: 0 1 auto;", css)
        tab_idx = css.index(".tab-button {")
        self.assertLess(tab_idx, generic_width_idx)

    def test_field_help_buttons_are_outside_title_wrapper(self) -> None:
        html = INDEX_HTML.read_text(encoding="utf-8")
        panel_start = html.index('data-tab-panel="asr_advanced"')
        panel_end = html.index('data-tab-panel="tools"', panel_start)
        panel_html = html[panel_start:panel_end]
        for match in re.finditer(r'<span class="inline-field-title">([\s\S]*?)</span>', panel_html):
            self.assertNotIn("field-help-btn", match.group(1))
        self.assertIn('<div class="inline-field annotated-field">', panel_html)
        self.assertIn('<div class="checkbox-row checkbox-row-with-help">', panel_html)

    def test_field_help_module_exports_mount(self) -> None:
        source = FIELD_HELP_JS.read_text(encoding="utf-8")
        self.assertIn("export function mountFieldHelpButtons", source)
        self.assertIn('getBoundingClientRect()', source)


if __name__ == "__main__":
    unittest.main()
