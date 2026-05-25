from __future__ import annotations

import unittest
from pathlib import Path

from backend.bootstrap_pip_pins import (
    ANTLR4_RUNTIME_WHEEL_NAME,
    OFFLINE_PYTHON_WHEELS_DIR,
    antlr4_runtime_satisfied,
    bundled_antlr4_wheel,
)


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
