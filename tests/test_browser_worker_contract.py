from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOOGLE_ASR_HTML = PROJECT_ROOT / "frontend" / "google_asr.html"
BROWSER_ASR_MANAGER_JS = PROJECT_ROOT / "frontend" / "js" / "browser-asr-session-manager.js"


class BrowserWorkerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = GOOGLE_ASR_HTML.read_text(encoding="utf-8")
        cls.manager_js = BROWSER_ASR_MANAGER_JS.read_text(encoding="utf-8")

    def test_hidden_or_minimized_window_warning_is_present(self) -> None:
        self.assertIn("hidden or minimized", self.html)
        self.assertIn("browser recognition can stall, end via onend", self.html)

    def test_worker_page_loads_external_session_manager(self) -> None:
        self.assertIn('/static/js/browser-asr-session-manager.js', self.html)

    def test_worker_page_keeps_only_ui_glue_and_uses_session_manager_for_runtime(self) -> None:
        self.assertNotIn("function ensureRecognition()", self.html)
        self.assertNotIn("function sendUpdate(payload)", self.html)
        self.assertNotIn("async function tryStartRecognition()", self.html)
        self.assertIn("sessionManager.applyRecognitionSettings()", self.html)
        self.assertIn("sessionManager.handleForceFinalizationSettingChange()", self.html)
        self.assertIn("sessionManager.ensureSocketConnected()", self.html)

    def test_terminal_errors_cancel_automatic_restart_but_audio_capture_is_recoverable(self) -> None:
        self.assertIn('"not-allowed"', self.manager_js)
        self.assertIn('"service-not-allowed"', self.manager_js)
        self.assertIn('"language-not-supported"', self.manager_js)
        self.assertIn("audio_capture_recovery", self.manager_js)
        self.assertIn("restart cancelled due to terminal error", self.manager_js)

    def test_normal_onend_uses_fast_rearm_and_watchdog_exists(self) -> None:
        self.assertIn("fastRearmDelayMs = 60", self.manager_js)
        self.assertIn('this._scheduleRecognitionRestart("onend", { useBackoff: false })', self.manager_js)
        self.assertIn("watchdog forced rearm", self.manager_js)
        self.assertIn("_runWatchdog()", self.manager_js)

    def test_worker_keeps_socket_reconnect_loop_and_backend_status_bridge(self) -> None:
        self.assertIn("ensureSocketConnected()", self.manager_js)
        self.assertIn("setTimeout(() => this.ensureSocketConnected(), this.socketReconnectDelayMs)", self.manager_js)
        self.assertIn('"browser_asr_status"', self.manager_js)
        self.assertIn("recognition.onend", self.manager_js)


if __name__ == "__main__":
    unittest.main()
