from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from desktop import launcher as launcher_module


class _FakeWindow:
    def __init__(self) -> None:
        self.destroyed = False
        self.loaded_urls: list[str] = []
        self.js_calls: list[str] = []
        self.events = SimpleNamespace(closed=_FakeEventHook())

    def destroy(self) -> None:
        self.destroyed = True

    def load_url(self, url: str) -> None:
        self.loaded_urls.append(url)

    def evaluate_js(self, script: str) -> None:
        self.js_calls.append(script)


class _FakeEventHook:
    def __iadd__(self, _handler):
        return self


class LauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.paths = SimpleNamespace(
            project_root=self.root,
            logs_dir=self.root / "logs",
            data_dir=self.root / "user-data",
            runtime_root=self.root / "runtime",
            bundle_root=self.root,
            install_profile_file=self.root / "install-profile.txt",
            venv_python=self.root / ".venv" / "Scripts" / "python.exe",
        )
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.runtime_root.mkdir(parents=True, exist_ok=True)
        self.paths.venv_python.parent.mkdir(parents=True, exist_ok=True)
        self.paths.venv_python.write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _launcher(self) -> launcher_module.DesktopLauncher:
        with mock.patch("desktop.launcher.detect_runtime_paths", return_value=self.paths):
            return launcher_module.DesktopLauncher()

    def test_is_port_in_use_detects_bound_socket(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            host, port = sock.getsockname()
            self.assertTrue(launcher_module._is_port_in_use(host, port))

    def test_format_port_error_includes_detected_owner(self) -> None:
        launcher = self._launcher()
        with mock.patch("desktop.launcher._describe_port_owner", return_value="Detected another process on port."):
            message = launcher._format_port_error()
        self.assertIn("127.0.0.1:8765", message)
        self.assertIn("Detected another process on port.", message)

    def test_run_returns_error_when_webview_start_fails(self) -> None:
        launcher = self._launcher()
        fake_window = _FakeWindow()
        fake_webview = SimpleNamespace(
            create_window=mock.Mock(return_value=fake_window),
            start=mock.Mock(side_effect=RuntimeError("webview boom")),
        )
        with mock.patch.dict(sys.modules, {"webview": fake_webview}), mock.patch("desktop.launcher._show_error_dialog") as dialog:
            result = launcher.run()

        self.assertEqual(result, 1)
        self.assertTrue(dialog.called)

    def test_bootstrap_stops_when_local_port_is_busy(self) -> None:
        launcher = self._launcher()
        window = _FakeWindow()
        with mock.patch("desktop.launcher._is_port_in_use", return_value=True), mock.patch(
            "desktop.launcher._show_error_dialog"
        ) as dialog:
            launcher.bootstrap(window)

        self.assertTrue(window.destroyed)
        self.assertIn("already in use", launcher._startup_error_message or "")
        self.assertTrue(dialog.called)

    def test_set_launch_option_accepts_minimal_remote_modes(self) -> None:
        launcher = self._launcher()

        self.assertTrue(launcher._set_launch_option("remote_controller"))
        self.assertEqual(launcher._selected_launch_mode(), "remote_controller")
        self.assertTrue(launcher._set_launch_option("remote_worker"))
        self.assertEqual(launcher._selected_launch_mode(), "remote_worker")
        self.assertFalse(launcher._set_launch_option("not-a-mode"))

    def test_wait_for_launch_option_selection_cancelled_when_window_shutdown(self) -> None:
        launcher = self._launcher()
        window = _FakeWindow()

        def close_soon() -> None:
            time.sleep(0.15)
            launcher.shutdown()

        threading.Thread(target=close_soon, daemon=True).start()
        with self.assertRaises(launcher_module.LaunchSelectionCancelled):
            with mock.patch("desktop.launcher.auto_detect_install_profile", return_value="cpu"):
                launcher._wait_for_launch_option_selection(window)

    def test_bootstrap_launch_selection_cancelled_skips_error_dialog(self) -> None:
        launcher = self._launcher()
        window = _FakeWindow()
        with mock.patch("desktop.launcher._is_port_in_use", return_value=False):
            with mock.patch.object(
                launcher,
                "_wait_for_launch_option_selection",
                side_effect=launcher_module.LaunchSelectionCancelled,
            ):
                with mock.patch("desktop.launcher._show_error_dialog") as dialog_mock:
                    launcher.bootstrap(window)
        self.assertIsNone(launcher._startup_error_message)
        dialog_mock.assert_not_called()

    def test_apply_startup_mode_to_config_persists_remote_worker_state(self) -> None:
        launcher = self._launcher()

        launcher._apply_startup_mode_to_config(
            launcher_module.STARTUP_MODE_LOCAL,
            launcher_module.LAUNCH_OPTION_NVIDIA,
            remote_role="worker",
            allow_lan=True,
        )

        payload = json.loads((self.paths.data_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["asr"]["mode"], "local")
        self.assertTrue(payload["asr"]["prefer_gpu"])
        self.assertTrue(payload["remote"]["enabled"])
        self.assertEqual(payload["remote"]["role"], "worker")
        self.assertTrue(payload["remote"]["lan"]["bind_enabled"])

    def test_browser_worker_window_keeps_address_bar(self) -> None:
        launcher = self._launcher()
        browser_path = self.root / "chrome.exe"
        browser_path.write_text("", encoding="utf-8")

        with (
            mock.patch.object(launcher, "_find_chromium_browser", return_value=browser_path),
            mock.patch.object(launcher, "_opt_out_chrome_power_throttling") as opt_out_mock,
            mock.patch("desktop.launcher.subprocess.Popen") as popen_mock,
        ):
            popen_mock.return_value = SimpleNamespace(pid=4242)
            launched = launcher._open_browser_worker_window("http://127.0.0.1:8765/google-asr")

        self.assertTrue(launched)
        args = popen_mock.call_args.args[0]
        self.assertIn("--new-window", args)
        self.assertIn("--no-first-run", args)
        self.assertIn("--no-default-browser-check", args)
        self.assertIn("--disable-default-apps", args)
        self.assertNotIn("--disable-extensions", args)
        self.assertNotIn("--disable-sync", args)
        self.assertNotIn("--allow-browser-signin=false", args)
        self.assertIn("--window-size=980,860", args)
        self.assertIn("--disable-backgrounding-occluded-windows", args)
        self.assertIn("--disable-renderer-backgrounding", args)
        self.assertIn("--disable-background-timer-throttling", args)
        self.assertIn("--noerrdialogs", args)
        self.assertIn("http://127.0.0.1:8765/google-asr", args)
        self.assertIn("--user-data-dir=" + str(self.paths.runtime_root / "browser-worker-profile-classic-chrome"), args)
        self.assertNotIn("--app=http://127.0.0.1:8765/google-asr", args)
        # Confirm Chrome feature disables for occlusion/efficiency/throttling are present
        disable_features_arg = next(
            (arg for arg in args if isinstance(arg, str) and arg.startswith("--disable-features=")),
            None,
        )
        self.assertIsNotNone(disable_features_arg, "expected a --disable-features= argument")
        features_csv = disable_features_arg.split("=", 1)[1]
        feature_list = set(features_csv.split(","))
        for feature in (
            "CalculateNativeWinOcclusion",
            "HighEfficiencyModeAvailable",
            "HeuristicMemorySaver",
            "IntensiveWakeUpThrottling",
            "GlobalMediaControls",
        ):
            self.assertIn(feature, feature_list, f"missing --disable-features entry: {feature}")
        # Confirm HIGH_PRIORITY_CLASS is set on the Popen creationflags
        creation_flags = popen_mock.call_args.kwargs.get("creationflags", 0)
        self.assertTrue(
            creation_flags & 0x00000080,
            f"expected HIGH_PRIORITY_CLASS bit (0x80) in creationflags, got {creation_flags:#x}",
        )
        # Confirm we also try to opt out of Windows 11 EcoQoS / Efficiency Mode
        opt_out_mock.assert_called_once_with(4242)

    def test_browser_worker_experimental_window_keeps_address_bar(self) -> None:
        launcher = self._launcher()
        browser_path = self.root / "chrome.exe"
        browser_path.write_text("", encoding="utf-8")

        with (
            mock.patch.object(launcher, "_find_chromium_browser", return_value=browser_path),
            mock.patch.object(launcher, "_opt_out_chrome_power_throttling") as opt_out_mock,
            mock.patch("desktop.launcher.subprocess.Popen") as popen_mock,
        ):
            popen_mock.return_value = SimpleNamespace(pid=4343)
            launched = launcher._open_external_url("http://127.0.0.1:8765/google-asr-experimental")

        self.assertTrue(launched)
        args = popen_mock.call_args.args[0]
        self.assertIn("--new-window", args)
        self.assertIn("--no-first-run", args)
        self.assertIn("--no-default-browser-check", args)
        self.assertIn("--disable-default-apps", args)
        self.assertNotIn("--disable-extensions", args)
        self.assertNotIn("--disable-sync", args)
        self.assertNotIn("--allow-browser-signin=false", args)
        self.assertIn("--window-size=980,860", args)
        self.assertIn("--disable-backgrounding-occluded-windows", args)
        self.assertIn("--disable-renderer-backgrounding", args)
        self.assertIn("--disable-background-timer-throttling", args)
        self.assertIn("--noerrdialogs", args)
        self.assertIn("http://127.0.0.1:8765/google-asr-experimental", args)
        self.assertIn(
            "--user-data-dir=" + str(self.paths.runtime_root / "browser-worker-profile-experimental-chrome"),
            args,
        )
        self.assertFalse(any(str(item).startswith("--app=") for item in args))
        creation_flags = popen_mock.call_args.kwargs.get("creationflags", 0)
        self.assertTrue(creation_flags & 0x00000080)
        opt_out_mock.assert_called_once_with(4343)

    def test_opt_out_chrome_power_throttling_is_best_effort_no_op_on_invalid_pid(self) -> None:
        launcher = self._launcher()
        # Should not raise even with bogus pid; this is a Windows-only best-effort path.
        launcher._opt_out_chrome_power_throttling(0)

    def test_launcher_migrates_legacy_root_logs(self) -> None:
        legacy_logs_dir = self.root / "user-data" / "logs"
        legacy_logs_dir.mkdir(parents=True, exist_ok=True)
        (legacy_logs_dir / "desktop-launcher.log").write_text("legacy", encoding="utf-8")

        launcher = self._launcher()

        self.assertTrue((launcher._paths.logs_dir / "desktop-launcher.log").exists())
        self.assertFalse(legacy_logs_dir.exists())


class LauncherBrowserPreferenceTests(unittest.TestCase):
    def test_ordered_browser_executable_names_returns_chrome_only(self) -> None:
        self.assertEqual(launcher_module.ordered_browser_executable_names("auto"), ("chrome.exe",))
        self.assertEqual(launcher_module.ordered_browser_executable_names("google_chrome"), ("chrome.exe",))

    def test_load_worker_launch_browser_preference_invalid_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "config.json"
            cfg.write_text(
                json.dumps({"asr": {"browser": {"worker_launch_browser": "nope"}}}),
                encoding="utf-8",
            )
            self.assertEqual(launcher_module._load_worker_launch_browser_preference(cfg), "auto")

    def test_load_worker_launch_browser_preference_chromium_maps_to_auto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "config.json"
            cfg.write_text(
                json.dumps({"asr": {"browser": {"worker_launch_browser": "chromium"}}}),
                encoding="utf-8",
            )
            self.assertEqual(launcher_module._load_worker_launch_browser_preference(cfg), "auto")


if __name__ == "__main__":
    unittest.main()
