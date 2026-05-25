"""Contract tests: desktop Browser Speech worker launch (TECHNICAL_ARCHITECTURE §11.1, §14.1)."""
from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PY = (PROJECT_ROOT / "desktop" / "launcher.py").read_text(encoding="utf-8")

# TECHNICAL_ARCHITECTURE §11.1 — Chrome stability flags for Web Speech worker windows.
REQUIRED_CHROME_DISABLED_FEATURES = (
    "CalculateNativeWinOcclusion",
    "HighEfficiencyModeAvailable",
    "HeuristicMemorySaver",
    "IntensiveWakeUpThrottling",
    "GlobalMediaControls",
)

REQUIRED_CHROME_ARGS = (
    "--new-window",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-session-crashed-bubble",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--user-data-dir=",
)

FORBIDDEN_WORKER_ARGS = (
    "--app=",
    "--disable-extensions",
    "--bwsi",
)


class DesktopBrowserWorkerLaunchContractTests(unittest.TestCase):
    def test_worker_paths_include_classic_and_experimental(self) -> None:
        self.assertIn('"/google-asr"', LAUNCHER_PY)
        self.assertIn('"/google-asr-experimental"', LAUNCHER_PY)

    def test_desktop_resolves_worker_to_chrome_only(self) -> None:
        self.assertIn('return ("chrome.exe",)', LAUNCHER_PY)
        self.assertIn('return resolved.name.lower() == "chrome.exe"', LAUNCHER_PY)
        self.assertIn('return "/google-asr"', LAUNCHER_PY)

    def test_worker_launch_browser_preference_normalizes_to_chrome(self) -> None:
        self.assertIn('allowed = {"auto", "google_chrome"}', LAUNCHER_PY)
        self.assertIn('if raw == "microsoft_edge":', LAUNCHER_PY)
        self.assertIn('raw = "google_chrome"', LAUNCHER_PY)

    def test_open_browser_worker_window_uses_required_chrome_flags(self) -> None:
        start = LAUNCHER_PY.index("def _open_browser_worker_window")
        end = LAUNCHER_PY.index("def _opt_out_chrome_power_throttling", start)
        block = LAUNCHER_PY[start:end]
        for feature in REQUIRED_CHROME_DISABLED_FEATURES:
            self.assertIn(feature, block, msg=f"missing disabled feature {feature}")
        for arg in REQUIRED_CHROME_ARGS:
            self.assertIn(arg, block, msg=f"missing launch arg {arg}")
        for forbidden in FORBIDDEN_WORKER_ARGS:
            self.assertNotIn(forbidden, block, msg=f"forbidden arg present: {forbidden}")
        self.assertIn("HIGH_PRIORITY_CLASS", block)
        self.assertIn("_opt_out_chrome_power_throttling", block)
        self.assertIn("isolated worker window with address bar", block)

    def test_power_throttling_opt_out_uses_process_information(self) -> None:
        start = LAUNCHER_PY.index("def _opt_out_chrome_power_throttling")
        end = LAUNCHER_PY.index("def _is_noise_backend_line", start)
        block = LAUNCHER_PY[start:end]
        self.assertIn("ProcessPowerThrottling", block)
        self.assertIn("SetProcessInformation", block)
        self.assertIn("StateMask = 0", block)

    def test_isolated_profiles_separate_classic_and_experimental(self) -> None:
        start = LAUNCHER_PY.index("def _browser_worker_profile_dir")
        end = LAUNCHER_PY.index("def _open_browser_worker_window", start)
        block = LAUNCHER_PY[start:end]
        self.assertIn('variant = "experimental"', block)
        self.assertIn("browser-worker-profile-", block)

    def test_external_url_routes_worker_pages_to_dedicated_launcher(self) -> None:
        start = LAUNCHER_PY.index("def _open_external_url")
        end = LAUNCHER_PY.index("def _format_port_error", start)
        block = LAUNCHER_PY[start:end]
        self.assertIn("_is_browser_worker_url", block)
        self.assertIn("_open_browser_worker_window", block)

    def test_browser_quick_start_skips_local_ai_bootstrap(self) -> None:
        bootstrap_start = LAUNCHER_PY.index("def bootstrap(self, window: Any)")
        bootstrap_end = LAUNCHER_PY.index("\n    def shutdown(self)", bootstrap_start)
        block = LAUNCHER_PY[bootstrap_start:bootstrap_end]
        local_idx = block.index("elif startup_mode == STARTUP_MODE_LOCAL:")
        else_idx = block.index("else:", local_idx)
        local_branch = block[local_idx:else_idx]
        browser_branch = block[else_idx:block.index("bootstrapper.cleanup_transient_runtime_files")]
        self.assertIn("ensure_local_asr_runtime", local_branch)
        self.assertIn("ensure_base_environment()", browser_branch)
        self.assertNotIn("ensure_local_asr_runtime", browser_branch)

    def test_profile_lock_and_browser_mode_on_quick_start(self) -> None:
        start = LAUNCHER_PY.index("def _apply_startup_mode_to_config")
        end = LAUNCHER_PY.index("def _normalize_external_url", start)
        block = LAUNCHER_PY[start:end]
        self.assertIn('asr["mode"] = STARTUP_MODE_BROWSER', block)
        self.assertIn('asr["desktop_profile_lock"] = DESKTOP_PROFILE_LOCK_BROWSER_SPEECH', block)
        self.assertIn("self._web_speech_only", block)

    def test_web_speech_only_skips_profile_panel(self) -> None:
        start = LAUNCHER_PY.index("def _wait_for_launch_option_selection")
        end = LAUNCHER_PY.index("def _apply_startup_mode_to_config", start)
        block = LAUNCHER_PY[start:end]
        self.assertIn("if self._web_speech_only:", block)
        self.assertIn("return STARTUP_MODE_BROWSER", block)

    def test_pywebview_profile_lives_under_runtime_root(self) -> None:
        self.assertIn('storage_path=str(self._paths.runtime_root / "pywebview-profile")', LAUNCHER_PY)


if __name__ == "__main__":
    unittest.main()
