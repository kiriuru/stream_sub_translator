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
DESKTOP_JS = PROJECT_ROOT / "frontend" / "js" / "desktop.js"


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
        cls.desktop_js = DESKTOP_JS.read_text(encoding="utf-8")

    def test_hidden_or_minimized_window_warning_is_present(self) -> None:
        self.assertIn("hidden or minimized", self.html)
        self.assertIn("recognition can stall", self.html)

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
        self.assertIn("normal_onend: 350", self.manager_js)
        self.assertIn("settings_change: 350", self.manager_js)
        self.assertIn("websocket_reconnect: 350", self.manager_js)
        self.assertIn("watchdog_stall: 750", self.manager_js)
        self.assertIn("session_cycle: 350", self.manager_js)
        self.assertIn("initialNoSpeechDelayMs = 350", self.manager_js)
        self.assertIn("maxNoSpeechDelayMs = 5000", self.manager_js)
        self.assertIn("initialNetworkBackoffMs = 1000", self.manager_js)
        self.assertIn("maxNetworkBackoffMs = 30000", self.manager_js)
        self.assertIn('"normal_onend"', self.manager_js)
        self.assertIn("watchdog forced rearm", self.manager_js)
        self.assertIn("_runWatchdog()", self.manager_js)
        self.assertIn("recognition.start deferred: recognition is stopping", self.manager_js)

    def test_supervisor_keeps_pending_start_generation_and_visibility_guards(self) -> None:
        self.assertIn("pendingStart", self.manager_js)
        self.assertIn("generationId", self.manager_js)
        self.assertIn("_isActiveGeneration(generationId)", self.manager_js)
        self.assertIn("capturedGeneration !== Number(this.state.generationId || 0)", self.manager_js)
        self.assertIn("document.hidden", self.manager_js)
        self.assertIn("_waitUntilDocumentVisibleForRecognition", self.manager_js)
        self.assertIn("_lastWebSpeechNetworkHintAtMs", self.manager_js)
        self.assertIn("startupInFlight", self.manager_js)
        self.assertIn('supervisor === "starting"', self.manager_js)
        self.assertIn('supervisor === "stopping"', self.manager_js)
        self.assertIn("maxStoppingMs = 2500", self.manager_js)
        self.assertIn("watchdog-stop", self.manager_js)
        self.assertIn("lastResultIndex", self.manager_js)
        self.assertIn("browserCyclePending", self.manager_js)
        self.assertIn("browserCycleCount", self.manager_js)
        self.assertIn("browserMinimumReconnectSuppressedCount", self.manager_js)
        self.assertIn("browserForcedFinalOnInterruptionCount", self.manager_js)
        self.assertIn("_forceFinalizeOnInterruption(", self.manager_js)
        self.assertIn("browser session age limit reached; controlled cycle requested", self.manager_js)
        self.assertIn("browser_recognition_interrupted", self.manager_js)
        self.assertIn("minimumReconnectIntervalMs = 500", self.manager_js)
        self.assertIn("maxBrowserSessionAgeMs = 180000", self.manager_js)
        self.assertIn("prepareCycleBeforeMs = 15000", self.manager_js)

    def test_manager_applies_screen_wake_lock_during_recognition(self) -> None:
        # Wake Lock keeps the OS from throttling the worker tab when display/system
        # would otherwise enter idle/sleep. Acquire on start, release on stop/destroy.
        self.assertIn("_acquireWakeLock", self.manager_js)
        self.assertIn("_releaseWakeLock", self.manager_js)
        self.assertIn("navigator.wakeLock.request", self.manager_js)
        self.assertIn('navigator.wakeLock.request("screen")', self.manager_js)
        self.assertIn('this._acquireWakeLock("user-start")', self.manager_js)
        self.assertIn('this._releaseWakeLock("user-stop")', self.manager_js)
        self.assertIn('this._releaseWakeLock("destroy")', self.manager_js)
        self.assertIn("wake_lock_active", self.manager_js)
        self.assertIn("wake_lock_supported", self.manager_js)

    def test_manager_runs_network_preflight_after_consecutive_network_errors(self) -> None:
        # After repeated "network" errors within a short window we probe
        # https://www.google.com/generate_204 once; on failure we mark the
        # supervisor terminally degraded ("recognition_network_unreachable")
        # so we stop looping forever on a dead network/VPN/firewall.
        self.assertIn("_registerNetworkErrorForPreflight", self.manager_js)
        self.assertIn("_runNetworkPreflight", self.manager_js)
        self.assertIn("https://www.google.com/generate_204", self.manager_js)
        self.assertIn("recognition_network_unreachable", self.manager_js)
        self.assertIn("network_error_burst_count", self.manager_js)
        self.assertIn("network_preflight_last_at_ms", self.manager_js)
        self.assertIn("network_preflight_last_ok", self.manager_js)

    def test_manager_emits_voice_below_recognition_threshold_health_signal(self) -> None:
        # When the mic clearly has voice-level RMS but Web Speech stays silent
        # and "no-speech" has accumulated, surface a distinct degraded reason
        # so operators see "voice present, Google not recognising" instead of
        # only the generic "web_speech_stalled".
        self.assertIn("voice_below_recognition_threshold", self.manager_js)
        self.assertIn("voiceBelowRecognitionRmsThreshold", self.manager_js)
        self.assertIn("voiceBelowRecognitionGraceMs", self.manager_js)

    def test_worker_keeps_socket_reconnect_loop_and_backend_status_bridge(self) -> None:
        self.assertIn("ensureSocketConnected()", self.manager_js)
        self.assertIn("restartDelayByReasonMs.websocket_reconnect", self.manager_js)
        self.assertIn('"browser_asr_status"', self.manager_js)
        self.assertIn('"browser_asr_control"', self.manager_js)
        self.assertIn("session_id", self.manager_js)
        self.assertIn("generation_id", self.manager_js)
        self.assertIn("provider_name", self.manager_js)
        self.assertIn("last_result_index", self.manager_js)
        self.assertIn("browser_session_age_ms", self.manager_js)
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
        self.assertIn("Web Speech Worker (Experimental)", self.experimental_html)

    def test_experimental_manager_uses_audio_track_start_and_default_fallback(self) -> None:
        self.assertIn("recognition.start(audioTrack)", self.experimental_manager_js)
        self.assertIn("recognition.start()", self.experimental_manager_js)
        self.assertIn('audioTrack.kind !== "audio"', self.experimental_manager_js)
        self.assertIn('audioTrack.readyState !== "live"', self.experimental_manager_js)
        self.assertNotIn("_ensureRecognition()", self.experimental_manager_js)
        self.assertNotIn("_scheduleRecognitionRestart(", self.experimental_manager_js)
        self.assertIn("async _performControlledStart(reason)", self.experimental_manager_js)
        self.assertIn("super.destroy();", self.experimental_manager_js)

    def test_experimental_manager_releases_tracks_on_stop_and_restart(self) -> None:
        self.assertIn("navigator.mediaDevices.getUserMedia", self.experimental_manager_js)
        self.assertIn("track.stop()", self.experimental_manager_js)
        self.assertIn('_releaseAudioTrack("stop")', self.experimental_manager_js)
        self.assertIn("pendingStart = true", self.experimental_manager_js)
        self.assertIn("experimental audio track open skipped while stopping", self.experimental_manager_js)
        self.assertIn("mediaTrackLeakGuardCount", self.experimental_manager_js)
        self.assertIn("getUserMediaCount", self.experimental_manager_js)
        self.assertIn("mediaTracksStoppedCount", self.experimental_manager_js)

    def test_experimental_page_mentions_audio_track_mode_and_fallback_behavior(self) -> None:
        self.assertIn("SpeechRecognition.start(audioTrack)", self.experimental_html)
        self.assertIn("fall back to normal start()", self.experimental_html)
        self.assertIn("loadBackendSettings: loadSettings", self.experimental_html)
        self.assertIn('window.addEventListener("pagehide"', self.experimental_html)
        self.assertIn("resolveBrowserLifecycleConfig(browserConfig)", self.experimental_html)
        self.assertIn("providerName: state.browserMode", self.experimental_html)

    def test_dashboard_exposes_desktop_worker_browser_selector(self) -> None:
        self.assertIn('id="recognition-worker-browser-select"', self.index_html)
        self.assertIn('id="recognition-worker-browser-web-note"', self.index_html)
        self.assertIn("worker_launch_browser", self.asr_panel_js)
        self.assertIn("controlsWorkerBrowserLaunch", self.asr_panel_js)
        self.assertIn("controlsWorkerBrowserLaunch", self.desktop_js)

    def test_local_provider_selector_only_lists_parakeet_variants(self) -> None:
        self.assertIn('id="local-asr-provider-hint"', self.index_html)
        self.assertIn("Backend providers are configured here for local microphone capture. Web Speech modes use the separate browser worker window.", self.index_html)
        local_select_pos = self.index_html.find('id="local-asr-provider-select"')
        self.assertGreater(local_select_pos, 0)
        local_select_end = self.index_html.find("</select>", local_select_pos)
        self.assertGreater(local_select_end, local_select_pos)
        local_provider_block = self.index_html[local_select_pos:local_select_end]
        self.assertNotIn('value="auto"', local_provider_block)
        self.assertNotIn("_".join(["google", "legacy", "http"]), self.index_html)
        self.assertIn("setElementVisibility(elements.localAsrProviderRow, !browserMode)", self.asr_panel_js)
        self.assertIn('draft.asr.mode = "local";', self.asr_panel_js)
        self.assertNotIn("_".join(["google", "legacy", "http"]), self.asr_panel_js)
        self.assertIn("if (result?.runtime && mode !== \"local\")", self.runtime_panel_js)
        self.assertNotIn("_".join(["google", "legacy", "http", "experimental"]), self.runtime_panel_js)


if __name__ == "__main__":
    unittest.main()
