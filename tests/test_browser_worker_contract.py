from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOOGLE_ASR_HTML = PROJECT_ROOT / "frontend" / "google_asr.html"
BROWSER_ASR_MANAGER_JS = PROJECT_ROOT / "frontend" / "js" / "browser-asr-session-manager.js"
GOOGLE_ASR_EXPERIMENTAL_HTML = PROJECT_ROOT / "frontend" / "google_asr_experimental.html"
BROWSER_ASR_AUDIO_TRACK_MANAGER_JS = (
    PROJECT_ROOT / "frontend" / "js" / "browser-asr-audio-track-session-manager.js"
)
RUNTIME_PANEL_JS = PROJECT_ROOT / "frontend" / "js" / "panels" / "runtime-panel.js"
ASR_PANEL_JS = PROJECT_ROOT / "frontend" / "js" / "panels" / "asr-panel.js"
INDEX_HTML = PROJECT_ROOT / "frontend" / "index.html"


class BrowserWorkerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = GOOGLE_ASR_HTML.read_text(encoding="utf-8")
        cls.manager_js = BROWSER_ASR_MANAGER_JS.read_text(encoding="utf-8")
        cls.experimental_html = GOOGLE_ASR_EXPERIMENTAL_HTML.read_text(encoding="utf-8")
        cls.experimental_manager_js = BROWSER_ASR_AUDIO_TRACK_MANAGER_JS.read_text(encoding="utf-8")
        cls.runtime_panel_js = RUNTIME_PANEL_JS.read_text(encoding="utf-8")
        cls.asr_panel_js = ASR_PANEL_JS.read_text(encoding="utf-8")
        cls.index_html = INDEX_HTML.read_text(encoding="utf-8")

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
        self.assertIn('"audio-capture"', self.manager_js)
        self.assertIn("audio_capture_recovery", self.manager_js)
        self.assertIn('this._setSupervisorState("fatal")', self.manager_js)

    def test_supervisor_uses_controlled_restart_and_watchdog_exists(self) -> None:
        self.assertIn("normal_onend: 200", self.manager_js)
        self.assertIn("settings_change: 200", self.manager_js)
        self.assertIn("websocket_reconnect: 300", self.manager_js)
        self.assertIn("watchdog_stall: 750", self.manager_js)
        self.assertIn("initialNoSpeechDelayMs = 1200", self.manager_js)
        self.assertIn("maxNoSpeechDelayMs = 5000", self.manager_js)
        self.assertIn("initialNetworkBackoffMs = 1000", self.manager_js)
        self.assertIn("maxNetworkBackoffMs = 10000", self.manager_js)
        self.assertIn('"normal_onend"', self.manager_js)
        self.assertIn("watchdog forced rearm", self.manager_js)
        self.assertIn("_runWatchdog()", self.manager_js)
        self.assertIn("recognition.start deferred: recognition is stopping", self.manager_js)

    def test_worker_keeps_socket_reconnect_loop_and_backend_status_bridge(self) -> None:
        self.assertIn("ensureSocketConnected()", self.manager_js)
        self.assertIn("restartDelayByReasonMs.websocket_reconnect", self.manager_js)
        self.assertIn('"browser_asr_status"', self.manager_js)
        self.assertIn('"browser_asr_control"', self.manager_js)
        self.assertIn("session_id", self.manager_js)
        self.assertIn("generation_id", self.manager_js)
        self.assertIn('"reload_settings"', self.manager_js)

    def test_google_asr_worker_prioritizes_local_storage_settings_but_mirrors_backend(self) -> None:
        self.assertIn('WORKER_SETTINGS_STORAGE_KEY = "sst.browser_worker.settings.v1"', self.html)
        self.assertIn("readWorkerSettingsFromLocalStorage()", self.html)
        self.assertIn("resolveWorkerSettings(backendBrowserConfig, storedWorkerSettings)", self.html)
        self.assertIn('window.localStorage.setItem(WORKER_SETTINGS_STORAGE_KEY, JSON.stringify(nextWorkerSettings))', self.html)
        self.assertIn('/api/settings/save', self.html)
        self.assertIn('storedWorkerSettings ? "localStorage+backend" : "backend"', self.html)

    def test_manager_emits_duplicate_and_mic_health_diagnostics(self) -> None:
        self.assertIn("duplicate_partial_suppressed", self.manager_js)
        self.assertIn("duplicate_final_suppressed", self.manager_js)
        self.assertIn("late_forced_final_suppressed", self.manager_js)
        self.assertIn("mic_track_ready_state", self.manager_js)
        self.assertIn("mic_track_muted", self.manager_js)
        self.assertIn("mic_rms", self.manager_js)
        self.assertIn("mic_active_recent_ms", self.manager_js)
        self.assertIn("web_speech_stalled", self.manager_js)
        self.assertIn("mic_silent", self.manager_js)
        self.assertIn("mic_track_unavailable", self.manager_js)

    def test_persisted_worker_log_whitelist_excludes_routine_restart_chatter(self) -> None:
        self.assertNotIn('"recognition.onend",', self.html)
        self.assertNotIn('"recognition.onstart",', self.html)
        self.assertNotIn('"restart scheduled",', self.html)
        self.assertIn('"watchdog forced rearm",', self.html)

    def test_experimental_worker_page_exists_and_loads_dedicated_audio_track_manager(self) -> None:
        self.assertIn("/static/js/browser-asr-audio-track-session-manager.js", self.experimental_html)
        self.assertIn("Browser Recognition Window (Experimental)", self.experimental_html)

    def test_experimental_manager_uses_audio_track_start_and_default_fallback(self) -> None:
        self.assertIn("recognition.start(audioTrack)", self.experimental_manager_js)
        self.assertIn("recognition.start()", self.experimental_manager_js)
        self.assertIn('audioTrack.kind !== "audio"', self.experimental_manager_js)
        self.assertIn('audioTrack.readyState !== "live"', self.experimental_manager_js)
        self.assertNotIn("_ensureRecognition()", self.experimental_manager_js)
        self.assertNotIn("_scheduleRecognitionRestart(", self.experimental_manager_js)
        self.assertIn("async _performControlledStart(reason)", self.experimental_manager_js)
        self.assertIn("super.destroy();", self.experimental_manager_js)

    def test_experimental_page_mentions_audio_track_mode_and_fallback_behavior(self) -> None:
        self.assertIn("SpeechRecognition.start(audioTrack)", self.experimental_html)
        self.assertIn("fall back to normal start()", self.experimental_html)
        self.assertIn("loadBackendSettings: loadSettings", self.experimental_html)
        self.assertIn('window.addEventListener("pagehide"', self.experimental_html)

    def test_local_google_legacy_provider_is_available_without_changing_browser_worker_start_gate(self) -> None:
        self.assertIn('value="google_legacy_http_experimental"', self.index_html)
        self.assertIn('id="local-asr-provider-hint"', self.index_html)
        self.assertIn("To use Google Legacy HTTP Speech Experimental, switch Recognition method to Local Parakeet.", self.index_html)
        self.assertNotIn('id="google-legacy-http-api-key"', self.index_html)
        self.assertIn("setElementVisibility(elements.localAsrProviderRow, true)", self.asr_panel_js)
        self.assertIn("if (result?.runtime && mode !== \"local\")", self.runtime_panel_js)
        self.assertNotIn("google_legacy_http_experimental &&", self.runtime_panel_js)


if __name__ == "__main__":
    unittest.main()
