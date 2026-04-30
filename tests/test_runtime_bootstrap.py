from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from desktop.runtime_bootstrap import RuntimeBootstrapper


class RuntimeBootstrapperSeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.bundle_root = self.root / "bundle"
        self.venv_python = self.root / ".venv" / "Scripts" / "python.exe"
        self.venv_python.parent.mkdir(parents=True, exist_ok=True)
        self.venv_python.write_text("", encoding="utf-8")
        self.logs: list[str] = []
        self.bootstrapper = RuntimeBootstrapper(
            paths=SimpleNamespace(
                bundle_root=self.bundle_root,
                venv_python=self.venv_python,
            ),
            log=self.logs.append,
            status=lambda _message: None,
            register_process=lambda _process: None,
            unregister_process=lambda _process: None,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_seed_offline_ai_packages_copies_vendor_lightning(self) -> None:
        vendor_root = self.bundle_root / "vendor" / "python-site-packages"
        (vendor_root / "lightning").mkdir(parents=True, exist_ok=True)
        (vendor_root / "lightning" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
        (vendor_root / "lightning-2.4.0.dist-info").mkdir(parents=True, exist_ok=True)
        (vendor_root / "lightning-2.4.0.dist-info" / "METADATA").write_text("Name: lightning\nVersion: 2.4.0\n", encoding="utf-8")

        self.bootstrapper._seed_offline_ai_packages()

        target_site_packages = self.root / ".venv" / "Lib" / "site-packages"
        self.assertTrue((target_site_packages / "lightning" / "__init__.py").exists())
        self.assertTrue((target_site_packages / "lightning-2.4.0.dist-info" / "METADATA").exists())
        self.assertTrue(any("Seeded offline AI package: lightning" in line for line in self.logs))


if __name__ == "__main__":
    unittest.main()
