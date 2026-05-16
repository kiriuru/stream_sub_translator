from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from desktop.launcher import _wait_for_http_ok

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DesktopLauncherStartupTests(unittest.TestCase):
    def test_dashboard_loaded_handler_does_not_call_get_current_url(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        start = launcher_py.index("def _on_desktop_window_loaded")
        end = launcher_py.index("\n    def _migrate_legacy_logs_dir", start)
        handler = launcher_py[start:end]
        code_lines = [
            line
            for line in handler.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        joined = "\n".join(code_lines)
        self.assertNotIn("get_current_url(", joined)
        self.assertIn("real_url", joined)

    def test_dashboard_opens_via_location_replace_not_load_url(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("def _navigate_to_dashboard", launcher_py)
        self.assertIn("window.location.replace", launcher_py)
        bootstrap_start = launcher_py.index("def bootstrap(self, window: Any)")
        bootstrap_end = launcher_py.index("\n    def shutdown(self)", bootstrap_start)
        bootstrap_body = launcher_py[bootstrap_start:bootstrap_end]
        self.assertIn("_navigate_to_dashboard(window", bootstrap_body)
        self.assertNotIn("window.load_url(self._context.dashboard_url)", bootstrap_body)

    def test_health_verify_logs_to_file_only(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        marker = "def verify_health_after_dashboard"
        start = launcher_py.index(marker)
        end = launcher_py.index("\n            threading.Thread", start)
        block = launcher_py[start:end]
        self.assertIn("self._write_log", block)
        self.assertNotIn("_publish_window_log", block)
    @patch("desktop.launcher.urlopen")
    @patch("desktop.launcher.time.sleep", return_value=None)
    def test_wait_for_http_ok_returns_on_success(self, _sleep: MagicMock, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        urlopen.return_value = response

        _wait_for_http_ok("http://127.0.0.1:8765/", timeout_seconds=5)

        urlopen.assert_called_once()

    @patch("desktop.launcher.urlopen")
    @patch("desktop.launcher.time.sleep", return_value=None)
    def test_wait_for_http_ok_retries_until_ready(self, _sleep: MagicMock, urlopen: MagicMock) -> None:
        failing = MagicMock(side_effect=OSError("connection refused"))
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        urlopen.side_effect = [failing, response]

        _wait_for_http_ok("http://127.0.0.1:8765/", timeout_seconds=5)

        self.assertEqual(urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
