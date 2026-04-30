from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from desktop import bootstrap_launcher as bootstrap_module


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


if __name__ == "__main__":
    unittest.main()
