from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.config import AppSettings, LocalConfigManager
from backend.core.config_migrations import CURRENT_CONFIG_VERSION, migrate_config
from backend.core.profile_manager import ProfileManager


class ConfigMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.manager = LocalConfigManager(AppSettings(data_dir=self.root / "user-data"))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_old_config_without_version_migrates_to_current_schema(self) -> None:
        migrated = self.manager.save(
            {
                "targets": ["en", "ja"],
                "translation": {
                    "enabled": True,
                    "provider": "google_translate_v2",
                    "provider_settings": {"google_translate_v2": {"api_key": "AIza-demo"}},
                },
                "subtitle_style": {"preset": "clean_default", "custom_presets": {"stream": {"label": "Stream"}}},
            }
        )

        self.assertEqual(migrated["config_version"], CURRENT_CONFIG_VERSION)
        self.assertIn("ui", migrated)
        self.assertIn("asr", migrated)
        self.assertIn("translation", migrated)
        self.assertFalse(migrated["remote"]["enabled"])
        self.assertEqual(migrated["translation"]["target_languages"], ["en", "ja"])
        self.assertIn("custom_presets", migrated["subtitle_style"])

    def test_migrate_config_renames_legacy_parakeet_provider(self) -> None:
        migrated = migrate_config(
            {
                "config_version": 2,
                "asr": {"provider_preference": "official_eu_parakeet_realtime"},
            }
        )

        self.assertEqual(migrated["config_version"], CURRENT_CONFIG_VERSION)
        self.assertEqual(migrated["asr"]["provider_preference"], "official_eu_parakeet_low_latency")

    def test_translation_settings_and_subtitle_style_are_preserved(self) -> None:
        migrated = self.manager.save(
            {
                "translation": {
                    "enabled": True,
                    "provider": "deepl",
                    "target_languages": ["en", "de"],
                    "timeout_ms": 15000,
                    "provider_settings": {
                        "deepl": {
                            "api_key": " secret-key ",
                            "api_url": " https://api-free.deepl.com/v2/translate ",
                        }
                    },
                },
                "subtitle_style": {
                    "preset": "clean_default",
                    "custom_presets": {
                        "stream": {
                            "label": "Stream",
                            "base": {"font_family": "Arial"},
                        }
                    },
                },
            }
        )

        self.assertTrue(migrated["translation"]["enabled"])
        self.assertEqual(migrated["translation"]["provider"], "deepl")
        self.assertEqual(migrated["translation"]["target_languages"], ["en", "de"])
        self.assertEqual(
            migrated["translation"]["provider_settings"]["deepl"]["api_url"],
            "https://api-free.deepl.com/v2/translate",
        )
        self.assertIn("stream", migrated["subtitle_style"]["custom_presets"])

    def test_google_legacy_http_shape_is_added_and_disabled_by_default(self) -> None:
        migrated = self.manager.save(
            {
                "asr": {
                    "mode": "local",
                    "provider_preference": "official_eu_parakeet_low_latency",
                }
            }
        )

        google_legacy_http = migrated["asr"]["google_legacy_http"]
        self.assertFalse(google_legacy_http["enabled"])
        self.assertEqual(google_legacy_http["language"], "ru-RU")
        self.assertEqual(google_legacy_http["connect_timeout_ms"], 10000)
        self.assertEqual(google_legacy_http["send_timeout_ms"], 10000)
        self.assertEqual(google_legacy_http["recv_timeout_ms"], 30000)
        self.assertEqual(google_legacy_http["max_queue_depth"], 50)
        self.assertEqual(google_legacy_http["endpoint_host"], "")
        self.assertEqual(google_legacy_http["pair_id_prefix"], "sst")

    def test_migrate_config_adds_google_legacy_http_shape_without_auto_selecting_provider(self) -> None:
        migrated = migrate_config(
            {
                "config_version": 4,
                "asr": {
                    "mode": "local",
                    "provider_preference": "official_eu_parakeet_low_latency",
                },
            }
        )

        self.assertEqual(migrated["config_version"], CURRENT_CONFIG_VERSION)
        self.assertEqual(migrated["asr"]["provider_preference"], "official_eu_parakeet_low_latency")
        self.assertIn("google_legacy_http", migrated["asr"])
        self.assertFalse(migrated["asr"]["google_legacy_http"]["enabled"])
        self.assertEqual(migrated["asr"]["google_legacy_http"]["pair_id_prefix"], "sst")

    def test_migrate_config_removes_legacy_http_api_key_and_keeps_pair_id_prefix(self) -> None:
        migrated = migrate_config(
            {
                "config_version": 4,
                "asr": {
                    "google_legacy_http": {
                        "enabled": True,
                        "language": "ru-RU",
                        "api_key": "legacy-secret",
                    }
                },
            }
        )

        self.assertEqual(migrated["config_version"], CURRENT_CONFIG_VERSION)
        self.assertNotIn("api_key", migrated["asr"]["google_legacy_http"])
        self.assertEqual(migrated["asr"]["google_legacy_http"]["pair_id_prefix"], "sst")

    def test_profiles_also_migrate_to_current_schema(self) -> None:
        profiles_dir = self.root / "profiles"
        manager = ProfileManager(profiles_dir, payload_normalizer=self.manager.normalize_profile_payload)
        legacy_profile = {
            "translation": {
                "enabled": True,
                "target_languages": ["fr"],
            },
            "asr": {
                "provider_preference": "official_eu_parakeet_realtime",
            },
            "subtitle_style": {
                "preset": "clean_default",
            },
        }
        (profiles_dir / "caster.json").parent.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "caster.json").write_text(json.dumps(legacy_profile, ensure_ascii=False, indent=2), encoding="utf-8")

        loaded = manager.load_profile("caster")

        self.assertEqual(loaded["config_version"], CURRENT_CONFIG_VERSION)
        self.assertEqual(loaded["profile"], "caster")
        self.assertEqual(loaded["asr"]["provider_preference"], "official_eu_parakeet_low_latency")
        self.assertFalse(loaded["remote"]["enabled"])
        self.assertEqual(loaded["translation"]["target_languages"], ["fr"])
        self.assertEqual(loaded["subtitle_style"]["preset"], "clean_default")


if __name__ == "__main__":
    unittest.main()
