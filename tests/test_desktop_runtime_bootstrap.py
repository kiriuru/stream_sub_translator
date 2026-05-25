from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from desktop.runtime_bootstrap import (
    DESKTOP_USER_DATA_DIRNAME,
    build_runtime_environment,
    detect_runtime_paths,
    ensure_runtime_layout,
    normalize_install_profile,
    quiet_import_check_snippet,
    _project_runtime_root,
)


class NormalizeInstallProfileTests(unittest.TestCase):
    def test_accepts_supported_values(self) -> None:
        self.assertEqual(normalize_install_profile("cpu"), "cpu")
        self.assertEqual(normalize_install_profile("CPU"), "cpu")
        self.assertEqual(normalize_install_profile(" nvidia "), "nvidia")

    def test_rejects_unsupported_values(self) -> None:
        self.assertIsNone(normalize_install_profile(""))
        self.assertIsNone(normalize_install_profile(None))
        self.assertIsNone(normalize_install_profile("auto"))
        self.assertIsNone(normalize_install_profile("rocm"))


class ProjectRuntimeRootTests(unittest.TestCase):
    def test_uses_explicit_env_override(self) -> None:
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            override = tmp / "custom-runtime"
            previous = os.environ.get("SST_RUNTIME_ROOT")
            os.environ["SST_RUNTIME_ROOT"] = str(override)
            try:
                resolved = _project_runtime_root(tmp / "project")
            finally:
                if previous is None:
                    os.environ.pop("SST_RUNTIME_ROOT", None)
                else:
                    os.environ["SST_RUNTIME_ROOT"] = previous
            self.assertEqual(resolved, override.resolve())

    def test_falls_back_to_public_documents(self) -> None:
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            previous_runtime = os.environ.pop("SST_RUNTIME_ROOT", None)
            previous_public = os.environ.get("PUBLIC")
            os.environ["PUBLIC"] = str(tmp)
            try:
                resolved = _project_runtime_root(tmp / "stream-sub-translator")
            finally:
                if previous_runtime is not None:
                    os.environ["SST_RUNTIME_ROOT"] = previous_runtime
                if previous_public is None:
                    os.environ.pop("PUBLIC", None)
                else:
                    os.environ["PUBLIC"] = previous_public
            self.assertTrue(
                str(resolved).startswith(
                    str((tmp / "Documents" / "StreamSubtitleTranslatorRuntime").resolve())
                ),
                msg=f"unexpected runtime root: {resolved}",
            )


class DetectRuntimePathsTests(unittest.TestCase):
    def test_paths_resolve_under_project_root(self) -> None:
        paths = detect_runtime_paths()
        self.assertTrue(paths.project_root.exists())
        self.assertTrue(paths.bundle_root.exists())
        self.assertTrue(str(paths.data_dir).endswith(DESKTOP_USER_DATA_DIRNAME))
        self.assertEqual(paths.logs_dir, paths.project_root / "logs")
        self.assertEqual(paths.install_profile_file, paths.data_dir / "install_profile.txt")
        self.assertEqual(paths.runtime_base_requirements.name, "requirements.runtime.base.txt")
        self.assertEqual(paths.runtime_ai_requirements.name, "requirements.runtime.ai.txt")
        self.assertEqual(paths.torch_cpu_requirements.name, "requirements.torch.cpu.txt")
        self.assertEqual(paths.torch_cuda_requirements.name, "requirements.torch.cuda.txt")


class BuildRuntimeEnvironmentTests(unittest.TestCase):
    def test_environment_keeps_runtime_caches_local(self) -> None:
        paths = detect_runtime_paths()
        env = build_runtime_environment(paths)
        self.assertEqual(env["PYTHONNOUSERSITE"], "1")
        self.assertEqual(env["PIP_CACHE_DIR"], str(paths.cache_root / "pip"))
        self.assertEqual(env["HF_HOME"], str(paths.cache_root / "huggingface"))
        self.assertEqual(env["TORCH_HOME"], str(paths.cache_root / "torch"))
        self.assertEqual(env["MPLCONFIGDIR"], str(paths.cache_root / "matplotlib"))
        self.assertEqual(env["TMP"], str(paths.temp_root))
        self.assertEqual(env["TEMP"], str(paths.temp_root))
        self.assertEqual(env["SST_PROJECT_ROOT"], str(paths.project_root))
        self.assertEqual(env["SST_BUNDLE_ROOT"], str(paths.bundle_root))
        if (paths.bundle_root / "backend").is_dir():
            self.assertEqual(env.get("SST_PYTHONPATH_ROOT"), str(paths.bundle_root))
        else:
            self.assertNotIn("SST_PYTHONPATH_ROOT", env)

    def test_environment_attaches_pythonpath_when_requested(self) -> None:
        paths = detect_runtime_paths()
        env = build_runtime_environment(paths, pythonpath_root=paths.project_root)
        self.assertEqual(env["SST_PYTHONPATH_ROOT"], str(paths.project_root))

    def test_environment_defaults_pythonpath_to_bundle_when_backend_present(self) -> None:
        from dataclasses import replace

        paths = detect_runtime_paths()
        if not (paths.bundle_root / "backend").is_dir():
            self.skipTest("bundle backend tree not present in this workspace")
        env = build_runtime_environment(paths)
        self.assertEqual(env["SST_PYTHONPATH_ROOT"], str(paths.bundle_root))


class EnsureRuntimeLayoutTests(unittest.TestCase):
    def test_creates_required_directories_under_fake_layout(self) -> None:
        from dataclasses import replace

        paths = detect_runtime_paths()
        with TemporaryDirectory() as raw:
            tmp_root = Path(raw)
            fake_project_root = tmp_root / "project"
            fake_runtime_root = tmp_root / "runtime"
            fake_paths = replace(
                paths,
                project_root=fake_project_root,
                data_dir=fake_project_root / DESKTOP_USER_DATA_DIRNAME,
                logs_dir=fake_project_root / "logs",
                runtime_root=fake_runtime_root,
                cache_root=fake_runtime_root / "cache",
                temp_root=fake_runtime_root / "tmp",
                fonts_dir=fake_project_root / "fonts",
                install_profile_file=fake_project_root / DESKTOP_USER_DATA_DIRNAME / "install_profile.txt",
            )
            ensure_runtime_layout(fake_paths)
            self.assertTrue(fake_paths.runtime_root.exists())
            self.assertTrue(fake_paths.cache_root.exists())
            self.assertTrue((fake_paths.cache_root / "pip").exists())
            self.assertTrue((fake_paths.cache_root / "huggingface" / "hub").exists())
            self.assertTrue((fake_paths.cache_root / "huggingface" / "transformers").exists())
            self.assertTrue(fake_paths.temp_root.exists())
            self.assertTrue(fake_paths.data_dir.exists())
            self.assertTrue((fake_paths.data_dir / "profiles").exists())
            self.assertTrue(fake_paths.logs_dir.exists())
            self.assertTrue((fake_paths.data_dir / "exports").exists())
            self.assertTrue((fake_paths.data_dir / "models").exists())
            self.assertTrue(fake_paths.fonts_dir.exists())


class QuietImportCheckSnippetTests(unittest.TestCase):
    def test_missing_import_exits_one_without_traceback(self) -> None:
        snippet = quiet_import_check_snippet("import definitely_not_a_real_module_xyz")
        completed = subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(completed.returncode, 1)
        combined = f"{completed.stdout}\n{completed.stderr}"
        self.assertNotIn("Traceback", combined)

    def test_present_import_exits_zero(self) -> None:
        snippet = quiet_import_check_snippet("import os")
        completed = subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
