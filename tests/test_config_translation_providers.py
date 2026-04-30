from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.config import AppSettings, LocalConfigManager


class ConfigTranslationProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = LocalConfigManager(AppSettings(data_dir=Path(self.temp_dir.name)))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_google_cloud_translation_v3_settings_are_normalized(self) -> None:
        normalized = self.manager._normalize(
            {
                "translation": {
                    "enabled": True,
                    "provider": "google_cloud_translation_v3",
                    "target_languages": ["en"],
                    "provider_settings": {
                        "google_cloud_translation_v3": {
                            "project_id": " demo-project ",
                            "access_token": " Bearer ya29.token-value ",
                            "location": " us-central1 ",
                            "model": " general/nmt ",
                        }
                    },
                }
            }
        )

        settings = normalized["translation"]["provider_settings"]["google_cloud_translation_v3"]
        self.assertEqual(normalized["translation"]["provider"], "google_cloud_translation_v3")
        self.assertEqual(settings["project_id"], "demo-project")
        self.assertEqual(settings["access_token"], "ya29.token-value")
        self.assertEqual(settings["location"], "us-central1")
        self.assertEqual(settings["model"], "general/nmt")

    def test_save_keeps_google_cloud_translation_v3_modern_config_shape(self) -> None:
        saved = self.manager.save(
            {
                "translation": {
                    "enabled": True,
                    "provider": "google_cloud_translation_v3",
                    "target_languages": ["en"],
                    "provider_settings": {
                        "google_cloud_translation_v3": {
                            "project_id": "demo-project",
                            "access_token": "Bearer ya29.saved-token",
                            "location": "global",
                            "model": "general/nmt",
                        }
                    },
                }
            }
        )

        provider_settings = saved["translation"]["provider_settings"]["google_cloud_translation_v3"]
        self.assertEqual(set(provider_settings.keys()), {"project_id", "access_token", "location", "model"})
        config_json = json.loads(self.manager.app_settings.config_path.read_text(encoding="utf-8"))
        config_provider_settings = config_json["translation"]["provider_settings"]["google_cloud_translation_v3"]
        self.assertEqual(
            config_provider_settings,
            {
                "project_id": "demo-project",
                "access_token": "ya29.saved-token",
                "location": "global",
                "model": "general/nmt",
            },
        )

    def test_removed_mymemory_provider_falls_back_to_google_translate_v2(self) -> None:
        normalized = self.manager._normalize(
            {
                "translation": {
                    "enabled": True,
                    "provider": "mymemory",
                    "target_languages": ["en"],
                }
            }
        )

        self.assertEqual(normalized["translation"]["provider"], "google_translate_v2")


if __name__ == "__main__":
    unittest.main()
