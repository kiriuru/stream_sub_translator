from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DiagnosticsI18nTests(unittest.TestCase):
    def test_format_diagnostic_metric_is_english_only(self) -> None:
        helpers_path = PROJECT_ROOT / "frontend" / "js" / "dashboard" / "helpers.js"
        source = helpers_path.read_text(encoding="utf-8")
        self.assertIn("formatDiagnosticMetric", source)
        self.assertIn('"not available"', source)

    def test_diagnostics_panel_uses_format_diagnostic_metric(self) -> None:
        panel_path = PROJECT_ROOT / "frontend" / "js" / "panels" / "diagnostics-panel.js"
        source = panel_path.read_text(encoding="utf-8")
        self.assertIn("formatDiagnosticMetric", source)
        self.assertIn("`provider latency: ${formatDiagnosticMetric", source)
        self.assertNotIn("getCurrentLocale() === \"ru\"", source)


if __name__ == "__main__":
    unittest.main()
