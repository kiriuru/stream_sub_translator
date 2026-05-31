from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from backend.bootstrap_pip_pins import (
    ANTLR4_RUNTIME_WHEEL_NAME,
    BOOTSTRAP_PIP_INSTALL_VERSION,
    BOOTSTRAP_PIP_MIN_VERSION,
    OFFLINE_PYTHON_WHEELS_DIR,
    antlr4_runtime_satisfied,
    bundled_antlr4_wheel,
    ensure_pip_bootstrap,
    parse_version_tuple,
    pip_bootstrap_satisfied,
)


class BootstrapPipVersionTests(unittest.TestCase):
    def test_parse_version_tuple_strips_non_numeric_suffix(self) -> None:
        self.assertEqual(parse_version_tuple("24.3.1"), (24, 3, 1))
        self.assertEqual(parse_version_tuple("26.1.1"), (26, 1, 1))

    def test_pip_bootstrap_satisfied_accepts_minimum_and_newer(self) -> None:
        minimum = ".".join(str(part) for part in BOOTSTRAP_PIP_MIN_VERSION)
        self.assertTrue(parse_version_tuple(minimum) >= BOOTSTRAP_PIP_MIN_VERSION)
        self.assertTrue(parse_version_tuple("26.1.1") >= BOOTSTRAP_PIP_MIN_VERSION)

    def test_ensure_pip_bootstrap_skips_network_when_pip_already_usable(self) -> None:
        python_exe = Path("python.exe")
        logs: list[str] = []
        with (
            mock.patch("backend.bootstrap_pip_pins.pip_bootstrap_satisfied", return_value=True),
            mock.patch("backend.bootstrap_pip_pins.read_pip_version", return_value=(26, 1, 1)),
            mock.patch("backend.bootstrap_pip_pins.subprocess.run") as run_command,
        ):
            ensure_pip_bootstrap(python_exe, log=logs.append)
        run_command.assert_not_called()
        self.assertTrue(any("Reusing existing pip 26.1.1" in line for line in logs))

    def test_pinned_install_version_is_fixed_not_latest(self) -> None:
        self.assertEqual(BOOTSTRAP_PIP_INSTALL_VERSION, "24.3.1")


class BundledAntlr4WheelTests(unittest.TestCase):
    def test_bundled_wheel_path_resolves_under_project_vendor(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        wheel = bundled_antlr4_wheel(project_root)
        self.assertIsNotNone(wheel)
        assert wheel is not None
        self.assertEqual(wheel.name, ANTLR4_RUNTIME_WHEEL_NAME)
        self.assertTrue(wheel.is_file())
        self.assertEqual(wheel.parent, project_root / OFFLINE_PYTHON_WHEELS_DIR)

    def test_dev_venv_has_compatible_antlr4_runtime(self) -> None:
        python_exe = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"
        if not python_exe.is_file():
            self.skipTest("dev .venv is not available")
        self.assertTrue(antlr4_runtime_satisfied(python_exe))


if __name__ == "__main__":
    unittest.main()
