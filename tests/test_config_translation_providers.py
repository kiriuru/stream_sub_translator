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

    def test_ui_language_round_trips_through_local_config(self) -> None:
        saved = self.manager.save(
            {
                "ui": {
                    "language": "ru",
                }
            }
        )

        self.assertEqual(saved["ui"]["language"], "ru")
        loaded = self.manager.load()
        self.assertEqual(loaded["ui"]["language"], "ru")
        config_json = json.loads(self.manager.app_settings.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config_json["ui"]["language"], "ru")

    def test_invalid_ui_language_normalizes_to_empty_value(self) -> None:
        normalized = self.manager._normalize(
            {
                "ui": {
                    "language": "de",
                }
            }
        )

        self.assertEqual(normalized["ui"]["language"], "")

    def test_main_settings_groups_round_trip_through_save_and_load(self) -> None:
        payload = {
            "profile": "streamer",
            "ui": {"language": "ru"},
            "audio": {"input_device_id": "mic-2"},
            "asr": {
                "mode": "browser_google",
                "provider_preference": "official_eu_parakeet_realtime",
                "prefer_gpu": False,
                "rnnoise_enabled": True,
                "rnnoise_strength": 42,
                "browser": {
                    "recognition_language": "en-US",
                    "interim_results": False,
                    "continuous_results": False,
                    "force_finalization_enabled": True,
                    "force_finalization_timeout_ms": 1800,
                },
                "realtime": {
                    "vad_mode": 2,
                    "partial_emit_interval_ms": 333,
                    "min_speech_ms": 190,
                    "silence_hold_ms": 210,
                    "finalization_hold_ms": 420,
                    "max_segment_ms": 6200,
                    "partial_min_delta_chars": 7,
                    "partial_coalescing_ms": 155,
                },
            },
            "translation": {
                "enabled": True,
                "provider": "google_translate_v2",
                "target_languages": ["en", "ja"],
                "timeout_ms": 12000,
                "queue_max_size": 9,
                "max_concurrent_jobs": 3,
                "provider_settings": {
                    "google_translate_v2": {"api_key": "AIza-test"},
                },
            },
            "subtitle_output": {
                "show_source": False,
                "show_translations": True,
                "max_translation_languages": 2,
                "display_order": ["ja", "source", "en"],
            },
            "subtitle_lifecycle": {
                "completed_block_ttl_ms": 5500,
                "completed_source_ttl_ms": 5100,
                "completed_translation_ttl_ms": 6300,
                "pause_to_finalize_ms": 420,
                "allow_early_replace_on_next_final": False,
                "sync_source_and_translation_expiry": False,
                "hard_max_phrase_ms": 6200,
            },
            "obs_closed_captions": {
                "enabled": True,
                "output_mode": "translation_1",
                "connection": {
                    "host": "127.0.0.1",
                    "port": 4455,
                    "password": "secret",
                },
                "debug_mirror": {
                    "enabled": True,
                    "input_name": "CC_DEBUG_ALT",
                    "send_partials": False,
                },
                "timing": {
                    "send_partials": False,
                    "partial_throttle_ms": 300,
                    "min_partial_delta_chars": 5,
                    "final_replace_delay_ms": 25,
                    "clear_after_ms": 3000,
                    "avoid_duplicate_text": True,
                },
            },
            "remote": {
                "enabled": True,
                "role": "controller",
                "session_id": "sess-1",
                "pair_code": "PAIR42",
                "lan": {
                    "bind_enabled": False,
                    "bind_host": "0.0.0.0",
                    "port": 9988,
                },
                "controller": {
                    "worker_url": "http://192.168.0.10:8876",
                    "connect_timeout_ms": 9000,
                    "reconnect_delay_ms": 2300,
                },
                "worker": {
                    "allow_unpaired": False,
                    "heartbeat_timeout_ms": 16000,
                },
            },
            "updates": {
                "enabled": True,
                "provider": "github_releases",
                "github_repo": "kiriuru/stream_sub_translator",
                "release_channel": "stable",
                "check_interval_hours": 24,
                "last_checked_utc": "2026-05-01T10:00:00Z",
                "latest_known_version": "0.2.9.9",
            },
        }

        saved = self.manager.save(payload)
        loaded = self.manager.load()

        self.assertEqual(loaded["profile"], "streamer")
        self.assertEqual(loaded["ui"]["language"], "ru")
        self.assertEqual(loaded["audio"]["input_device_id"], "mic-2")
        self.assertEqual(loaded["asr"]["mode"], "browser_google")
        self.assertFalse(loaded["asr"]["prefer_gpu"])
        self.assertEqual(loaded["asr"]["browser"]["recognition_language"], "en-US")
        self.assertFalse(loaded["asr"]["browser"]["continuous_results"])
        self.assertEqual(loaded["translation"]["provider"], "google_translate_v2")
        self.assertEqual(loaded["translation"]["target_languages"], ["en", "ja"])
        self.assertEqual(loaded["translation"]["timeout_ms"], 12000)
        self.assertEqual(loaded["subtitle_output"]["display_order"], ["ja", "source", "en"])
        self.assertFalse(loaded["subtitle_output"]["show_source"])
        self.assertEqual(loaded["subtitle_lifecycle"]["pause_to_finalize_ms"], 420)
        self.assertFalse(loaded["subtitle_lifecycle"]["allow_early_replace_on_next_final"])
        self.assertTrue(loaded["obs_closed_captions"]["enabled"])
        self.assertEqual(loaded["obs_closed_captions"]["output_mode"], "translation_1")
        self.assertEqual(loaded["obs_closed_captions"]["debug_mirror"]["input_name"], "CC_DEBUG_ALT")
        self.assertTrue(loaded["remote"]["enabled"])
        self.assertEqual(loaded["remote"]["role"], "controller")
        self.assertEqual(loaded["remote"]["controller"]["worker_url"], "http://192.168.0.10:8876")
        self.assertTrue(loaded["updates"]["enabled"])
        self.assertEqual(loaded["updates"]["github_repo"], "kiriuru/stream_sub_translator")
        self.assertEqual(loaded["updates"]["latest_known_version"], "0.2.9.9")
        self.assertEqual(saved, loaded)

if __name__ == "__main__":
    unittest.main()
