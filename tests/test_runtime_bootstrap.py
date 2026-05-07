from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from desktop.runtime_bootstrap import RuntimeBootstrapper, detect_runtime_paths, ensure_runtime_layout


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

    def test_detect_runtime_paths_places_logs_under_user_data(self) -> None:
        fake_bundle_root = self.root / "bundle-root"
        fake_bundle_root.mkdir(parents=True, exist_ok=True)

        with (
            mock.patch("desktop.runtime_bootstrap.sys.executable", str(self.root / "Stream Subtitle Translator.exe")),
            mock.patch("desktop.runtime_bootstrap.sys.frozen", True, create=True),
            mock.patch("desktop.runtime_bootstrap.sys._MEIPASS", str(fake_bundle_root), create=True),
        ):
            paths = detect_runtime_paths()

        self.assertEqual(paths.project_root, self.root)
        self.assertEqual(paths.data_dir, self.root / "user-data")
        self.assertEqual(paths.logs_dir, self.root / "user-data" / "logs")

    def test_ensure_runtime_layout_migrates_legacy_root_logs_to_user_data(self) -> None:
        bundle_root = self.root / "bundle"
        bundled_data_dir = bundle_root / "backend" / "data" / "models"
        bundled_data_dir.mkdir(parents=True, exist_ok=True)
        (bundled_data_dir / "README.txt").write_text("model docs", encoding="utf-8")
        (bundle_root / "backend" / "data" / "config.example.json").write_text("{}", encoding="utf-8")
        (bundle_root / "backend" / "data" / "dictionary_overrides.example.json").write_text("{}", encoding="utf-8")

        legacy_logs_dir = self.root / "logs"
        legacy_logs_dir.mkdir(parents=True, exist_ok=True)
        (legacy_logs_dir / "backend.log").write_text("legacy-backend", encoding="utf-8")
        (legacy_logs_dir / "runtime-events.jsonl").write_text("legacy-runtime", encoding="utf-8")

        paths = SimpleNamespace(
            project_root=self.root,
            bundle_root=bundle_root,
            data_dir=self.root / "user-data",
            logs_dir=self.root / "user-data" / "logs",
            runtime_root=self.root / "runtime",
            cache_root=self.root / "runtime" / "cache",
            temp_root=self.root / "runtime" / "tmp",
            frontend_dir=bundle_root / "frontend",
            overlay_dir=bundle_root / "overlay",
            fonts_dir=self.root / "fonts",
        )

        ensure_runtime_layout(paths)

        self.assertTrue((paths.logs_dir / "backend.log").exists())
        self.assertTrue((paths.logs_dir / "runtime-events.jsonl").exists())
        self.assertFalse(legacy_logs_dir.exists())
        self.assertTrue((paths.data_dir / "models" / "README.txt").exists())


if __name__ == "__main__":
    unittest.main()
