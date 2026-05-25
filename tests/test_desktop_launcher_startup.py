from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from desktop.launcher import (
    RUNTIME_METRICS_LOG_PREFIX,
    _format_runtime_metrics_log_line,
    _runtime_metrics_progress_signature,
    _wait_for_http_ok,
)

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
        self.assertIn("_dashboard_location_url", launcher_py)

    def test_dashboard_resize_uses_js_location_href(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        start = launcher_py.index("def _dashboard_location_url")
        end = launcher_py.index("\n    def _apply_dashboard_resize", start)
        block = launcher_py[start:end]
        self.assertIn("window.location.href", block)
        self.assertIn("real_url", block)

    def test_run_does_not_skip_splash_with_immediate_venv_handoff(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        run_start = launcher_py.index("def run(self) -> int:")
        run_end = launcher_py.index("\n\ndef main()", run_start)
        run_body = launcher_py[run_start:run_end]
        self.assertNotIn("_try_immediate_venv_handoff_from_saved_local_profile()", run_body)

    def test_desktop_api_exposes_native_runtime_stop(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("def request_runtime_stop(self)", launcher_py)

    def test_desktop_api_exposes_native_runtime_start(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("def request_runtime_start(", launcher_py)

    def test_local_asr_bootstrap_does_not_reexec_venv_launcher(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        bootstrap_start = launcher_py.index("def bootstrap(self, window: Any)")
        bootstrap_end = launcher_py.index("\n    def shutdown(self)", bootstrap_start)
        bootstrap_body = launcher_py[bootstrap_start:bootstrap_end]
        self.assertNotIn("_reexec_into_venv_python_for_local_asr(", bootstrap_body)
        self.assertNotIn("_needs_venv_python_handoff(", bootstrap_body)

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
        self.assertIn("_apply_dashboard_resize", block)
        self.assertNotIn("_publish_window_log", block)

    def test_format_runtime_metrics_log_line_includes_vad_and_asr_counters(self) -> None:
        line = _format_runtime_metrics_log_line(
            {
                "status": "listening",
                "metrics": {
                    "vad_segments_partial": 4,
                    "vad_segments_final": 2,
                    "asr_queue_depth": 1,
                    "partial_updates_emitted": 7,
                    "finals_emitted": 2,
                    "in_flight_transcribe_count": 0,
                    "vad_dropped_segments": 0,
                },
                "asr_diagnostics": {
                    "requested_device": "2",
                    "selected_device": "cuda",
                    "sample_rate": 16000,
                    "model_loaded": True,
                    "device_active": "cpu",
                },
            }
        )
        self.assertTrue(line.startswith(RUNTIME_METRICS_LOG_PREFIX))
        self.assertIn("status=listening", line)
        self.assertIn("device=2", line)
        self.assertIn("capture_sr=16000", line)
        self.assertIn("model_loaded=True", line)
        self.assertIn("exec_device=cpu", line)
        self.assertIn("vad_partial=4", line)
        self.assertIn("vad_final=2", line)
        self.assertIn("asr_queue=1", line)
        self.assertIn("partials=7", line)
        self.assertIn("finals=2", line)

    def test_runtime_metrics_progress_signature_tracks_counter_changes(self) -> None:
        baseline = {
            "metrics": {
                "vad_segments_partial": 0,
                "vad_segments_final": 0,
                "asr_queue_depth": 0,
                "partial_updates_emitted": 0,
                "finals_emitted": 0,
                "in_flight_transcribe_count": 0,
                "vad_dropped_segments": 0,
            }
        }
        updated = {
            "metrics": {
                **baseline["metrics"],
                "vad_segments_partial": 3,
                "partial_updates_emitted": 1,
            }
        }
        self.assertNotEqual(
            _runtime_metrics_progress_signature(baseline),
            _runtime_metrics_progress_signature(updated),
        )

    def test_launcher_starts_runtime_metrics_monitor_after_dashboard(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        bootstrap_start = launcher_py.index("def bootstrap(self, window: Any)")
        bootstrap_end = launcher_py.index("\n    def shutdown(self)", bootstrap_start)
        bootstrap_body = launcher_py[bootstrap_start:bootstrap_end]
        self.assertIn("_start_runtime_metrics_monitor()", bootstrap_body)
        self.assertIn("def _runtime_metrics_monitor_loop", launcher_py)
        self.assertIn(RUNTIME_METRICS_LOG_PREFIX, launcher_py)

    def test_schedule_dashboard_resize_waits_longer_for_desktop_url(self) -> None:
        launcher_py = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")
        start = launcher_py.index("def _schedule_dashboard_resize")
        end = launcher_py.index("\n    def _on_desktop_window_loaded", start)
        block = launcher_py[start:end]
        self.assertIn("max_attempts = 180", block)
        self.assertIn("navigation fallback", block)

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
