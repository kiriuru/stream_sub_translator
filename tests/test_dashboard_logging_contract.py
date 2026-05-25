from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGING_JS = PROJECT_ROOT / "frontend" / "js" / "dashboard" / "logging.js"
UI_TRACE_JS = PROJECT_ROOT / "frontend" / "js" / "dashboard" / "ui-trace.js"
RUNTIME_ACTIONS_JS = PROJECT_ROOT / "frontend" / "js" / "dashboard" / "actions" / "runtime-actions.js"


class DashboardLoggingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.logging_js = LOGGING_JS.read_text(encoding="utf-8")
        cls.ui_trace_js = UI_TRACE_JS.read_text(encoding="utf-8")
        cls.runtime_actions_js = RUNTIME_ACTIONS_JS.read_text(encoding="utf-8")

    def test_runtime_status_persistence_is_limited_to_major_states(self) -> None:
        self.assertIn('normalized.startsWith("[runtime] status ->")', self.logging_js)
        self.assertIn('"[runtime] status -> idle"', self.logging_js)
        self.assertIn('"[runtime] status -> starting"', self.logging_js)
        self.assertIn('"[runtime] status -> error"', self.logging_js)
        self.assertIn('"[runtime] status -> listening"', self.logging_js)

    def test_ui_trace_module_exports_visual_state_helpers(self) -> None:
        self.assertIn("export function buildRuntimeVisualSnapshot", self.ui_trace_js)
        self.assertIn("export function traceRuntimeVisualState", self.ui_trace_js)
        self.assertIn("listening_without_partials", self.ui_trace_js)

    def test_runtime_actions_emit_ui_trace(self) -> None:
        self.assertIn("traceRuntimeVisualState", self.runtime_actions_js)
        self.assertIn("traceRuntimeStatusTransition", self.runtime_actions_js)


if __name__ == "__main__":
    unittest.main()
