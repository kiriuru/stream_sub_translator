from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.config import AppSettings, LocalConfigManager
from backend.core.config_migrations import CURRENT_CONFIG_VERSION, migrate_config
from backend.core.profile_manager import ProfileManager


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _removed_provider_value() -> str:
    return "_".join(["google", "legacy", "http", "experimental"])


def _removed_provider_key() -> str:
    return "_".join(["google", "legacy", "http"])


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

        self.assertIn("source_text_replacement", migrated)
        self.assertFalse(migrated["source_text_replacement"]["enabled"])
        self.assertIn("ui", migrated)
        self.assertIn("asr", migrated)
        self.assertIn("translation", migrated)
        self.assertFalse(migrated["remote"]["enabled"])
        self.assertEqual(migrated["translation"]["target_languages"], ["en", "ja"])
        self.assertEqual(
            migrated["translation"]["lines"],
            [
                {
                    "slot_id": "translation_1",
                    "enabled": True,
                    "target_lang": "en",
                    "provider": "google_translate_v2",
                    "label": "EN",
                },
                {
                    "slot_id": "translation_2",
                    "enabled": True,
                    "target_lang": "ja",
                    "provider": "google_translate_v2",
                    "label": "JA",
                },
            ],
        )
        self.assertIn("custom_presets", migrated["subtitle_style"])

    def test_load_recovers_from_corrupt_json(self) -> None:
        config_path = self.manager.app_settings.config_path
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{not: json", encoding="utf-8")

        recovered = self.manager.load()

        self.assertIsInstance(recovered, dict)
        self.assertEqual(recovered["config_version"], CURRENT_CONFIG_VERSION)
        self.assertTrue(config_path.exists())

    def test_migrate_config_renames_legacy_parakeet_provider(self) -> None:
        migrated = migrate_config(
            {
                "config_version": 2,
                "asr": {"provider_preference": "official_eu_parakeet_realtime"},
            }
        )

        self.assertEqual(migrated["config_version"], CURRENT_CONFIG_VERSION)
        self.assertEqual(migrated["asr"]["provider_preference"], "official_eu_parakeet_low_latency")

    def test_removed_legacy_provider_preference_migrates_to_low_latency_parakeet(self) -> None:
        migrated = migrate_config(
            {
                "config_version": CURRENT_CONFIG_VERSION,
                "asr": {
                    "mode": "local",
                    "provider_preference": _removed_provider_value(),
                },
            }
        )

        self.assertEqual(migrated["asr"]["mode"], "local")
        self.assertEqual(migrated["asr"]["provider_preference"], "official_eu_parakeet_low_latency")

    def test_removed_legacy_asr_section_is_dropped_during_migration(self) -> None:
        migrated = migrate_config(
            {
                "config_version": CURRENT_CONFIG_VERSION,
                "asr": {
                    "mode": "local",
                    "provider_preference": _removed_provider_value(),
                    _removed_provider_key(): {
                        "enabled": True,
                        "api_key": "deprecated-secret",
                        "host_override": "https://example.test",
                    },
                },
            }
        )

        self.assertEqual(migrated["config_version"], CURRENT_CONFIG_VERSION)
        self.assertEqual(migrated["asr"]["provider_preference"], "official_eu_parakeet_low_latency")
        self.assertNotIn(_removed_provider_key(), migrated["asr"])

    def test_manager_normalization_does_not_resurrect_removed_legacy_asr_section(self) -> None:
        saved = self.manager.save(
            {
                "asr": {
                    "mode": "local",
                    "provider_preference": _removed_provider_value(),
                    _removed_provider_key(): {
                        "enabled": True,
                        "api_key": "deprecated-secret",
                    },
                }
            }
        )

        self.assertEqual(saved["asr"]["provider_preference"], "official_eu_parakeet_low_latency")
        self.assertNotIn(_removed_provider_key(), saved["asr"])

    def test_config_schema_excludes_removed_legacy_provider(self) -> None:
        schema_json = (PROJECT_ROOT / "backend" / "data" / "config.schema.json").read_text(encoding="utf-8")
        example_json = (PROJECT_ROOT / "backend" / "data" / "config.example.json").read_text(encoding="utf-8")
        self.assertNotIn(_removed_provider_key(), schema_json)
        self.assertNotIn(_removed_provider_value(), schema_json)
        self.assertNotIn(_removed_provider_key(), example_json)
        self.assertNotIn(_removed_provider_value(), example_json)

    def test_profiles_also_migrate_to_current_schema(self) -> None:
        profiles_dir = self.root / "profiles"
        manager = ProfileManager(profiles_dir, payload_normalizer=self.manager.normalize_profile_payload)
        legacy_profile = {
            "translation": {
                "enabled": True,
                "target_languages": ["fr"],
            },
            "asr": {
                "provider_preference": _removed_provider_value(),
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
        self.assertEqual(loaded["translation"]["lines"][0]["slot_id"], "translation_1")
        self.assertEqual(loaded["subtitle_style"]["preset"], "clean_default")

    def test_migration_maps_legacy_display_order_to_translation_slots(self) -> None:
        migrated = migrate_config(
            {
                "config_version": 5,
                "translation": {
                    "enabled": True,
                    "provider": "google_translate_v2",
                    "target_languages": ["en", "ja"],
                },
                "subtitle_output": {
                    "display_order": ["ja", "source", "en"],
                },
            }
        )

        self.assertEqual(migrated["subtitle_output"]["display_order"], ["translation_2", "source", "translation_1"])

    def test_migration_keeps_duplicate_target_languages_when_lines_exist(self) -> None:
        migrated = migrate_config(
            {
                "config_version": 5,
                "translation": {
                    "enabled": True,
                    "provider": "google_translate_v2",
                    "lines": [
                        {
                            "slot_id": "translation_1",
                            "enabled": True,
                            "target_lang": "en",
                            "provider": "google_translate_v2",
                        },
                        {
                            "slot_id": "translation_2",
                            "enabled": True,
                            "target_lang": "en",
                            "provider": "openai",
                            "label": "",
                        },
                    ],
                },
                "subtitle_output": {
                    "display_order": ["translation_2", "translation_1"],
                },
            }
        )

        self.assertEqual([line["target_lang"] for line in migrated["translation"]["lines"]], ["en", "en"])
        self.assertEqual([line["provider"] for line in migrated["translation"]["lines"]], ["google_translate_v2", "openai"])
        self.assertEqual(migrated["translation"]["target_languages"], ["en"])
        self.assertEqual(migrated["subtitle_output"]["display_order"], ["translation_2", "translation_1", "source"])

    def test_overlay_compact_preset_normalizes_to_stacked_plus_compact_flag(self) -> None:
        saved = self.manager.save(
            {
                "overlay": {
                    "preset": "compact",
                }
            }
        )
        self.assertEqual(saved["overlay"]["preset"], "stacked")
        self.assertTrue(saved["overlay"]["compact"])

    def test_worker_launch_browser_invalid_value_maps_to_auto(self) -> None:
        saved_invalid = self.manager.save({"asr": {"browser": {"worker_launch_browser": "safari"}}})
        self.assertEqual(saved_invalid["asr"]["browser"]["worker_launch_browser"], "auto")

    def test_worker_launch_browser_chromium_maps_to_auto(self) -> None:
        saved = self.manager.save({"asr": {"browser": {"worker_launch_browser": "chromium"}}})
        self.assertEqual(saved["asr"]["browser"]["worker_launch_browser"], "auto")


if __name__ == "__main__":
    unittest.main()
