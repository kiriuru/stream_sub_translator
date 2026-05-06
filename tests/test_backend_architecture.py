from __future__ import annotations

import json
import unittest

from backend import app as app_module
from backend.core.api_errors import build_error_response


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


if __name__ == "__main__":
    unittest.main()
