from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGING_JS = PROJECT_ROOT / "frontend" / "js" / "dashboard" / "logging.js"


class DashboardLoggingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.logging_js = LOGGING_JS.read_text(encoding="utf-8")

    def test_runtime_status_persistence_is_limited_to_major_states(self) -> None:
        self.assertIn('normalized.startsWith("[runtime] status ->")', self.logging_js)
        self.assertIn('"[runtime] status -> idle"', self.logging_js)
        self.assertIn('"[runtime] status -> starting"', self.logging_js)
        self.assertIn('"[runtime] status -> error"', self.logging_js)


if __name__ == "__main__":
    unittest.main()
