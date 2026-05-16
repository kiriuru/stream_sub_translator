from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.config import AppSettings, LocalConfigManager
from backend.config.defaults import build_default_config
from backend.schemas.config_schema import UiConfig


class UiLayoutConfigTests(unittest.TestCase):
    def test_ui_config_defaults_to_standard_layout(self) -> None:
        ui = UiConfig()
        self.assertEqual(ui.layout, "standard")
        self.assertFalse(ui.show_remote_tools)

    def test_default_config_includes_layout(self) -> None:
        payload = build_default_config(prefer_gpu_default=False)
        self.assertEqual(payload["ui"]["layout"], "standard")
        self.assertFalse(payload["ui"]["show_remote_tools"])

    def test_config_manager_preserves_ui_layout_on_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = LocalConfigManager(AppSettings(data_dir=Path(tmp) / "user-data"))
            saved = manager.save(
                {
                    **build_default_config(prefer_gpu_default=False),
                    "ui": {
                        "language": "ru",
                        "layout": "compact",
                        "show_remote_tools": True,
                        "theme": "dark",
                        "palette": {
                            "accent": "#6cc7ff",
                            "accent_secondary": "#ff6ce6",
                            "accent_tertiary": "#7ce3ad",
                        },
                    },
                }
            )
            self.assertEqual(saved["ui"]["layout"], "compact")
            self.assertTrue(saved["ui"]["show_remote_tools"])
            reloaded = manager.load()
            self.assertEqual(reloaded["ui"]["layout"], "compact")
            self.assertTrue(reloaded["ui"]["show_remote_tools"])


if __name__ == "__main__":
    unittest.main()
