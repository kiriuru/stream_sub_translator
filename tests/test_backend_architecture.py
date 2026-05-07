from __future__ import annotations

import json
import importlib
import unittest
from pathlib import Path

from backend import app as app_module
from backend.core.api_errors import build_error_response


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BackendArchitectureTests(unittest.TestCase):
    def test_app_state_exposes_centralized_paths_and_services(self) -> None:
        state = app_module.app.state

        self.assertTrue(hasattr(state, "paths"))
        self.assertTrue(hasattr(state, "runtime_service"))
        self.assertTrue(hasattr(state, "settings_service"))
        self.assertTrue(hasattr(state, "asr_service"))
        self.assertTrue(hasattr(state, "translation_service"))
        self.assertTrue(hasattr(state, "diagnostics_service"))
        self.assertTrue(hasattr(state, "export_service"))
        self.assertTrue(hasattr(state, "overlay_service"))
        self.assertTrue(hasattr(state, "model_manager"))
        self.assertEqual(state.paths.user_data_dir.name, "user-data")
        self.assertEqual(state.paths.models_dir.name, "models")

    def test_error_response_shape_is_frontend_friendly(self) -> None:
        response = build_error_response(
            code="MODEL_CORRUPT",
            message="Parakeet model checksum mismatch.",
            status_code=409,
            details={"expected_sha256": "abc123", "actual_sha256": "def456"},
            recommended_action="Run model repair.",
        )

        body = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(body["ok"], False)
        self.assertEqual(body["error"]["code"], "MODEL_CORRUPT")
        self.assertEqual(body["error"]["message"], "Parakeet model checksum mismatch.")
        self.assertEqual(body["error"]["details"]["expected_sha256"], "abc123")
        self.assertEqual(body["error"]["recommended_action"], "Run model repair.")

    def test_runtime_and_config_refactor_entrypoints_exist(self) -> None:
        expected_paths = [
            PROJECT_ROOT / "backend" / "config" / "__init__.py",
            PROJECT_ROOT / "backend" / "config" / "defaults.py",
            PROJECT_ROOT / "backend" / "config" / "secrets.py",
            PROJECT_ROOT / "backend" / "config" / "normalizers" / "asr.py",
            PROJECT_ROOT / "backend" / "config" / "normalizers" / "browser.py",
            PROJECT_ROOT / "backend" / "config" / "normalizers" / "translation.py",
            PROJECT_ROOT / "backend" / "config" / "normalizers" / "obs.py",
            PROJECT_ROOT / "backend" / "config" / "normalizers" / "remote.py",
            PROJECT_ROOT / "backend" / "config" / "normalizers" / "subtitles.py",
            PROJECT_ROOT / "backend" / "core" / "runtime_orchestrator.py",
            PROJECT_ROOT / "backend" / "core" / "runtime" / "audio_runtime_controller.py",
            PROJECT_ROOT / "backend" / "core" / "runtime" / "asr_runtime_controller.py",
            PROJECT_ROOT / "backend" / "core" / "runtime" / "translation_runtime_coordinator.py",
            PROJECT_ROOT / "backend" / "core" / "runtime" / "output_fanout_coordinator.py",
            PROJECT_ROOT / "backend" / "core" / "runtime" / "runtime_metrics_collector.py",
            PROJECT_ROOT / "backend" / "core" / "runtime" / "runtime_status_builder.py",
            PROJECT_ROOT / "backend" / "translation" / "engine.py",
            PROJECT_ROOT / "backend" / "translation" / "registry.py",
            PROJECT_ROOT / "backend" / "translation" / "readiness.py",
            PROJECT_ROOT / "backend" / "translation" / "providers" / "google_v2.py",
            PROJECT_ROOT / "backend" / "translation" / "providers" / "google_v3.py",
            PROJECT_ROOT / "backend" / "translation" / "providers" / "azure.py",
            PROJECT_ROOT / "backend" / "translation" / "providers" / "deepl.py",
            PROJECT_ROOT / "backend" / "translation" / "providers" / "libretranslate.py",
            PROJECT_ROOT / "backend" / "translation" / "providers" / "openai_compatible.py",
            PROJECT_ROOT / "backend" / "translation" / "providers" / "experimental_google_web.py",
            PROJECT_ROOT / "backend" / "asr" / "parakeet" / "model_installer.py",
            PROJECT_ROOT / "backend" / "asr" / "parakeet" / "runtime_loader.py",
            PROJECT_ROOT / "backend" / "asr" / "parakeet" / "device_diagnostics.py",
            PROJECT_ROOT / "backend" / "asr" / "parakeet" / "providers" / "base.py",
            PROJECT_ROOT / "backend" / "asr" / "parakeet" / "providers" / "official.py",
            PROJECT_ROOT / "backend" / "asr" / "parakeet" / "providers" / "realtime.py",
            PROJECT_ROOT / "backend" / "asr" / "parakeet" / "mock_provider.py",
        ]
        missing = [str(path.relative_to(PROJECT_ROOT)) for path in expected_paths if not path.exists()]
        self.assertEqual(missing, [])

    def test_translation_and_parakeet_shim_entrypoints_import(self) -> None:
        from backend.asr.parakeet.model_installer import ensure_official_eu_parakeet_model
        from backend.translation.registry import build_default_provider_registry

        self.assertTrue(callable(ensure_official_eu_parakeet_model))
        self.assertIn("google_translate_v2", build_default_provider_registry())

    def test_runtime_orchestrator_and_subtitle_router_import_cleanly(self) -> None:
        runtime_module = importlib.import_module("backend.core.runtime_orchestrator")
        subtitle_module = importlib.import_module("backend.core.subtitle_router")

        self.assertTrue(hasattr(runtime_module, "RuntimeOrchestrator"))
        self.assertTrue(hasattr(subtitle_module, "SubtitleRouter"))
        self.assertIs(subtitle_module.RuntimeOrchestrator, runtime_module.RuntimeOrchestrator)


if __name__ == "__main__":
    unittest.main()
