from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from desktop import bootstrap_launcher_web_only as web_only_module


class BootstrapLauncherWebOnlyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.launcher = web_only_module.WebOnlyBootstrapLauncher()
        self.launcher._paths = SimpleNamespace(
            runtime_exe=root / "runtime.exe",
            exe_dir=root,
            logs_dir=root / "logs",
            log_path=root / "logs" / "bootstrap-launcher.log",
        )
        self.launcher._log = lambda message: None
        self.launcher._status = lambda status, detail=None: None
        self.launcher._paths.runtime_exe.write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_launch_runtime_forwards_web_speech_only_flag(self) -> None:
        with mock.patch("desktop.bootstrap_launcher.subprocess.Popen") as popen_mock:
            self.launcher._launch_runtime()
        args = popen_mock.call_args.args[0]
        self.assertEqual(args[1], "--web-speech-only")

    def test_launch_runtime_does_not_duplicate_web_speech_only_flag(self) -> None:
        with mock.patch("desktop.bootstrap_launcher.subprocess.Popen") as popen_mock:
            self.launcher._launch_runtime("--web-speech-only", "--debug-webview")
        args = popen_mock.call_args.args[0]
        self.assertEqual(args.count("--web-speech-only"), 1)


if __name__ == "__main__":
    unittest.main()
