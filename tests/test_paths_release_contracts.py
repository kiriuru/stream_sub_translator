from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.config import AppSettings
from backend.core.paths import AppPaths, detect_app_paths, ensure_app_layout
from backend import runtime_paths


class PathsReleaseContractTests(unittest.TestCase):
    def test_runtime_paths_reexports_detect_and_run_paths(self) -> None:
        self.assertIs(runtime_paths.detect_runtime_paths, detect_app_paths)
        self.assertIsInstance(runtime_paths.RUNTIME_PATHS, AppPaths)

    def test_detect_app_paths_with_sst_project_root_uses_root_logs_and_user_data_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "release test folder"
            root.mkdir(parents=True, exist_ok=True)
            env = {"SST_PROJECT_ROOT": str(root)}
            with mock.patch.dict(os.environ, env, clear=False):
                paths = detect_app_paths()
            self.assertEqual(paths.project_root, root.resolve())
            self.assertEqual(paths.user_data_dir, root / "user-data")
            self.assertEqual(paths.logs_dir, root / "logs")
            self.assertEqual(paths.models_dir, root / "user-data" / "models")

    def test_detect_app_paths_prefers_bundle_backend_over_missing_project_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "install"
            bundle = root / "app-runtime"
            (bundle / "backend").mkdir(parents=True)
            env = {
                "SST_PROJECT_ROOT": str(root),
                "SST_BUNDLE_ROOT": str(bundle),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                paths = detect_app_paths()
            self.assertEqual(paths.backend_root, (bundle / "backend").resolve())
            self.assertFalse((root / "backend").exists())

    def test_ensure_app_layout_creates_models_under_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            root.mkdir(parents=True, exist_ok=True)
            bundle = root / "bundle"
            (bundle / "backend" / "data").mkdir(parents=True, exist_ok=True)
            (bundle / "backend" / "data" / "models").mkdir(parents=True, exist_ok=True)
            (bundle / "backend" / "data" / "config.example.json").write_text("{}", encoding="utf-8")
            (bundle / "backend" / "data" / "dictionary_overrides.example.json").write_text("{}", encoding="utf-8")
            (bundle / "backend" / "data" / "models" / "README.txt").write_text("models", encoding="utf-8")
            paths = AppPaths(
                project_root=root,
                bundle_root=bundle,
                backend_root=root / "backend",
                frontend_root=bundle / "frontend",
                overlay_root=bundle / "overlay",
                fonts_dir=root / "fonts",
                user_data_dir=root / "user-data",
                profiles_dir=root / "user-data" / "profiles",
                logs_dir=root / "logs",
                secrets_dir=root / "user-data" / "secrets",
                models_dir=root / "user-data" / "models",
                debug_dir=root / "user-data" / "debug",
                debug_asr_segments_dir=root / "user-data" / "debug" / "asr-segments",
                session_db_path=root / "user-data" / "session-log.sqlite3",
                runtime_dir=root / "runtime",
                cache_root=root / "runtime" / "cache",
                temp_root=root / "runtime" / "tmp",
                portable_mode=True,
                safe_mode=False,
            )
            ensure_app_layout(paths)
            self.assertTrue(paths.models_dir.is_dir())
            self.assertTrue((paths.models_dir / "README.txt").exists())
            self.assertTrue(paths.logs_dir.is_dir())

    def test_app_settings_default_bind_localhost(self) -> None:
        settings = AppSettings()
        self.assertEqual(settings.app_host, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
