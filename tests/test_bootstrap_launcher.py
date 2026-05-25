from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from desktop import bootstrap_launcher as bootstrap_module
from desktop.bootstrap_payload import PayloadManifest


class _FakeUi:
    def __init__(self, action: str | None) -> None:
        self._action = action
        self.updates: list[tuple[str, str | None]] = []

    def consume_action(self) -> str | None:
        action = self._action
        self._action = None
        return action

    def update(self, status: str, detail: str | None = None) -> None:
        self.updates.append((status, detail))

    def close(self) -> None:
        return


class BootstrapLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.launcher = object.__new__(bootstrap_module.BootstrapLauncher)
        self.launcher._paths = SimpleNamespace(
            logs_dir=root / "logs",
            log_path=root / "logs" / "bootstrap-launcher.log",
            exe_dir=root,
        )
        self.launcher._log = lambda message: None

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_poll_ui_actions_sets_repair_flag(self) -> None:
        self.launcher._ui = _FakeUi("repair")
        args = argparse.Namespace(repair=False, reset_runtime=False)

        self.launcher._poll_ui_actions(args)

        self.assertTrue(args.repair)
        self.assertFalse(args.reset_runtime)

    def test_poll_ui_actions_sets_reset_flag(self) -> None:
        self.launcher._ui = _FakeUi("reset")
        args = argparse.Namespace(repair=False, reset_runtime=False)

        self.launcher._poll_ui_actions(args)

        self.assertFalse(args.repair)
        self.assertTrue(args.reset_runtime)

    def test_migrate_legacy_logs_dir_keeps_logs_in_root(self) -> None:
        legacy_logs_dir = self.launcher._paths.exe_dir / "logs"
        legacy_logs_dir.mkdir(parents=True, exist_ok=True)
        (legacy_logs_dir / "bootstrap-launcher.log").write_text("legacy", encoding="utf-8")

        self.launcher._migrate_legacy_logs_dir()

        self.assertTrue((self.launcher._paths.logs_dir / "bootstrap-launcher.log").exists())
        # When target logs_dir is already root/logs, the migration is a no-op.
        self.assertTrue(legacy_logs_dir.exists())

    def test_maybe_prompt_update_skip_continues_bootstrap(self) -> None:
        class _UiSkip:
            def prompt_update_available(self, **kwargs: object) -> str:
                return "skip"

        launcher = object.__new__(bootstrap_module.BootstrapLauncher)
        launcher._paths = self.launcher._paths
        launcher._ui = _UiSkip()
        launcher._log = lambda _m: None
        launcher._status = lambda *_a, **_k: None
        manifest = PayloadManifest(
            app_version="0.1.0",
            release_track="stable",
            runtime_entrypoint=".sst-runtime.exe",
            install_marker="app-runtime/.install-complete",
            files=[],
        )
        with mock.patch.object(launcher, "_fetch_latest_release", return_value=("9.9.9", "https://example.com/release")):
            with mock.patch("desktop.bootstrap_launcher.os.startfile") as startfile:
                cont = launcher._maybe_prompt_update(manifest)
        self.assertTrue(cont)
        startfile.assert_not_called()

    def test_maybe_prompt_update_download_opens_url_and_aborts(self) -> None:
        class _UiDownload:
            def prompt_update_available(self, **kwargs: object) -> str:
                return "download"

        launcher = object.__new__(bootstrap_module.BootstrapLauncher)
        launcher._paths = self.launcher._paths
        launcher._ui = _UiDownload()
        launcher._log = lambda _m: None
        launcher._status = lambda *_a, **_k: None
        manifest = PayloadManifest(
            app_version="0.1.0",
            release_track="stable",
            runtime_entrypoint=".sst-runtime.exe",
            install_marker="app-runtime/.install-complete",
            files=[],
        )
        with mock.patch.object(launcher, "_fetch_latest_release", return_value=("9.9.9", "https://example.com/release")):
            with mock.patch("desktop.bootstrap_launcher.os.startfile") as startfile:
                cont = launcher._maybe_prompt_update(manifest)
        self.assertFalse(cont)
        startfile.assert_called_once_with("https://example.com/release")


if __name__ == "__main__":
    unittest.main()
