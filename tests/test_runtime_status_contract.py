from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend import app as app_module
from helpers import AppStateSandbox


class RuntimeStatusContractTests(unittest.TestCase):
    def test_runtime_status_exposes_typed_runtime_sections(self) -> None:
        config = {
            "config_version": 5,
            "source_lang": "ru",
            "asr": {"mode": "local", "provider_preference": "official_eu_parakeet_low_latency"},
            "translation": {"enabled": True, "provider": "google_translate_v2", "target_languages": ["en"]},
            "subtitle_output": {"show_source": True, "show_translations": True, "display_order": ["source", "en"]},
            "overlay": {"preset": "single", "compact": False},
            "remote": {"enabled": False, "role": "disabled"},
        }
        with AppStateSandbox(config=config) as _sandbox, TestClient(app_module.app) as client:
            payload = client.get("/api/runtime/status").json()

        self.assertIn("running", payload)
        self.assertIn("starting", payload)
        self.assertIn("phase", payload)
        self.assertIn("asr", payload)
        self.assertIn("translation", payload)
        self.assertIn("overlay", payload)
        self.assertIn("obs_captions", payload)
        self.assertIn("metrics", payload)
        self.assertIn("active_config_source", payload)
        self.assertIn("active_config_persisted", payload)
        self.assertIn("active_config_hash", payload)
        self.assertIsInstance(payload["asr"], dict)
        self.assertIsInstance(payload["translation"], dict)
        self.assertEqual(payload["phase"], "idle")
        self.assertEqual(payload["overlay"]["preset"], "single")
        self.assertEqual(payload["translation"]["target_languages"], ["en"])
        self.assertEqual(payload["active_config_source"], "disk")
        self.assertTrue(payload["active_config_persisted"])
        self.assertIsInstance(payload["active_config_hash"], str)


if __name__ == "__main__":
    unittest.main()
