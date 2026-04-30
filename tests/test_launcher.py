from __future__ import annotations

import socket
import tempfile
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

    def destroy(self) -> None:
        self.destroyed = True

    def load_url(self, url: str) -> None:
        self.loaded_urls.append(url)

    def evaluate_js(self, script: str) -> None:
        self.js_calls.append(script)


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

    def test_run_returns_error_when_single_instance_guard_is_already_held(self) -> None:
        launcher = self._launcher()
        with mock.patch.object(launcher, "_acquire_single_instance_guard", return_value=False), mock.patch(
            "desktop.launcher._show_error_dialog"
        ) as dialog:
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


if __name__ == "__main__":
    unittest.main()
