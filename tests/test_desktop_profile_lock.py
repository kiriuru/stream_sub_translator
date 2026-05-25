from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.config import AppSettings, LocalConfigManager
from backend.config.normalizers.asr import normalize_asr_config
from desktop import launcher as launcher_module


def _is_locked(config: dict | None, desktop: dict | None = None) -> bool:
    """Python mirror of frontend/js/dashboard/desktop-profile-lock.js."""
    payload = config if isinstance(config, dict) else {}
    asr = payload.get("asr", {}) if isinstance(payload.get("asr"), dict) else {}
    lock = str(asr.get("desktop_profile_lock", "") or "").lower()
    if lock == "browser_speech":
        return True
    ctx = desktop if isinstance(desktop, dict) else {}
    if not ctx.get("desktop_mode"):
        return False
    if ctx.get("web_speech_only"):
        return True
    return str(ctx.get("startup_mode", "") or "").lower() == "browser_google"


class DesktopProfileLockLogicTests(unittest.TestCase):
    def test_lock_from_config_field(self) -> None:
        self.assertTrue(
            _is_locked({"asr": {"desktop_profile_lock": "browser_speech", "mode": "browser_google"}})
        )

    def test_lock_from_desktop_startup_mode(self) -> None:
        self.assertTrue(
            _is_locked(
                {"asr": {"mode": "local"}},
                {"desktop_mode": True, "startup_mode": "browser_google"},
            )
        )

    def test_lock_from_web_speech_only_flag(self) -> None:
        self.assertTrue(
            _is_locked(
                {"asr": {"mode": "local"}},
                {"desktop_mode": True, "web_speech_only": True},
            )
        )

    def test_not_locked_for_local_ai_desktop_session(self) -> None:
        self.assertFalse(
            _is_locked(
                {"asr": {"mode": "local"}},
                {"desktop_mode": True, "startup_mode": "local"},
            )
        )


class DesktopProfileLockBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = LocalConfigManager(AppSettings(data_dir=Path(self.temp_dir.name)))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_normalize_asr_forces_browser_mode_when_lock_present(self) -> None:
        defaults = self.manager.default_config()["asr"]
        normalized = normalize_asr_config(
            {"mode": "local", "desktop_profile_lock": "browser_speech"},
            defaults=defaults,
        )
        self.assertEqual(normalized["mode"], "browser_google")
        self.assertEqual(normalized["desktop_profile_lock"], "browser_speech")

    def test_config_manager_roundtrip_preserves_lock(self) -> None:
        saved = self.manager.save(
            {
                "asr": {
                    "mode": "browser_google",
                    "desktop_profile_lock": "browser_speech",
                }
            }
        )
        self.assertEqual(saved["asr"]["desktop_profile_lock"], "browser_speech")
        loaded = self.manager.load()
        self.assertEqual(loaded["asr"]["desktop_profile_lock"], "browser_speech")
        self.assertEqual(loaded["asr"]["mode"], "browser_google")

    def test_save_with_local_mode_and_lock_upgrades_to_browser(self) -> None:
        saved = self.manager.save(
            {
                "asr": {
                    "mode": "local",
                    "desktop_profile_lock": "browser_speech",
                }
            }
        )
        self.assertEqual(saved["asr"]["mode"], "browser_google")
        self.assertEqual(saved["asr"]["desktop_profile_lock"], "browser_speech")


class DesktopProfileLockLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.paths = type(
            "Paths",
            (),
            {
                "project_root": self.root,
                "logs_dir": self.root / "logs",
                "data_dir": self.root / "user-data",
                "runtime_root": self.root / "runtime",
                "bundle_root": self.root,
                "install_profile_file": self.root / "install-profile.txt",
                "venv_python": self.root / ".venv" / "Scripts" / "python.exe",
            },
        )()
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _launcher(self, *, web_speech_only: bool = False) -> launcher_module.DesktopLauncher:
        with mock.patch("desktop.launcher.detect_runtime_paths", return_value=self.paths):
            return launcher_module.DesktopLauncher(web_speech_only=web_speech_only)

    def test_apply_startup_mode_sets_lock_for_browser_quick_start(self) -> None:
        launcher = self._launcher()
        launcher._apply_startup_mode_to_config(launcher_module.STARTUP_MODE_BROWSER, "cpu")
        payload = json.loads((self.paths.data_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["asr"]["mode"], "browser_google")
        self.assertEqual(payload["asr"]["desktop_profile_lock"], "browser_speech")

    def test_apply_startup_mode_clears_lock_for_gpu_session(self) -> None:
        config_path = self.paths.data_dir / "config.json"
        config_path.write_text(
            json.dumps({"asr": {"mode": "browser_google", "desktop_profile_lock": "browser_speech"}}),
            encoding="utf-8",
        )
        launcher = self._launcher()
        launcher._apply_startup_mode_to_config(
            launcher_module.STARTUP_MODE_LOCAL,
            launcher_module.LAUNCH_OPTION_NVIDIA,
        )
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["asr"]["mode"], "local")
        self.assertNotIn("desktop_profile_lock", payload["asr"])

    def test_web_speech_only_launcher_sets_lock_even_if_mode_local(self) -> None:
        launcher = self._launcher(web_speech_only=True)
        launcher._apply_startup_mode_to_config(launcher_module.STARTUP_MODE_BROWSER, "cpu")
        payload = json.loads((self.paths.data_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["asr"]["desktop_profile_lock"], "browser_speech")


class DesktopProfileLockFrontendContractTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.lock_js = (root / "frontend" / "js" / "dashboard" / "desktop-profile-lock.js").read_text(
            encoding="utf-8"
        )
        self.asr_panel_js = (root / "frontend" / "js" / "panels" / "asr-panel.js").read_text(encoding="utf-8")
        self.asr_panel_render_js = (root / "frontend" / "js" / "panels" / "asr" / "asr-panel-render.js").read_text(
            encoding="utf-8"
        )
        self.actions_js = (root / "frontend" / "js" / "dashboard" / "actions" / "config-actions.js").read_text(
            encoding="utf-8"
        )
        self.normalizer_js = (root / "frontend" / "js" / "normalizers" / "config-normalizer.js").read_text(
            encoding="utf-8"
        )
        self.main_js = (root / "frontend" / "js" / "main.js").read_text(encoding="utf-8")
        self.desktop_js = (root / "frontend" / "js" / "desktop.js").read_text(encoding="utf-8")

    def test_frontend_module_exports_lock_helpers(self) -> None:
        self.assertIn("export function isDesktopBrowserQuickStartLocked", self.lock_js)
        self.assertIn("export function applyDesktopProfileLockToAsrConfig", self.lock_js)
        self.assertIn("export function syncRecognitionModeSelectLock", self.lock_js)
        self.assertIn("localOption.remove()", self.lock_js)

    def test_asr_panel_removes_local_option_instead_of_only_disabling(self) -> None:
        combined_asr = self.asr_panel_js + "\n" + self.asr_panel_render_js
        self.assertIn("syncRecognitionModeSelectLock(elements.modeSelect, quickStartLocked)", combined_asr)
        self.assertNotIn("option.hidden = quickStartLocked", combined_asr)

    def test_actions_apply_lock_on_set_config(self) -> None:
        self.assertIn("applyDesktopProfileLockToAsrConfig(normalizeConfigShape(payload))", self.actions_js)

    def test_normalizer_forces_browser_mode_when_lock_present(self) -> None:
        self.assertIn('normalized.asr.desktop_profile_lock = "browser_speech"', self.normalizer_js)
        self.assertIn("normalized.asr.mode = \"browser_google\"", self.normalizer_js)

    def test_dashboard_mounts_before_blocking_on_desktop_bridge(self) -> None:
        mount_pos = self.main_js.find("mountAsrPanel(")
        load_pos = self.main_js.find(".loadInitialData()")
        self.assertGreater(mount_pos, 0)
        self.assertGreater(load_pos, 0)
        self.assertLess(mount_pos, load_pos)
        self.assertNotIn("await window.DesktopBridge?.getContext", self.main_js)

    def test_desktop_bridge_does_not_block_ui_on_missing_pywebview(self) -> None:
        self.assertIn("scheduleContextRefresh", self.desktop_js)
        self.assertIn("immediateDesktopContext", self.desktop_js)
        get_context_block = self.desktop_js.split("async function getContext()", 1)[1].split("async function ", 1)[0]
        self.assertNotIn("await waitForPywebviewApi", get_context_block)


if __name__ == "__main__":
    unittest.main()
