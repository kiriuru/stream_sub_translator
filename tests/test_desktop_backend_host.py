from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from desktop.backend_host import (
    VENV_LAUNCHER_REEXEC_ENV,
    _windows_handoff_creationflags,
    build_backend_subprocess_bootstrap,
    build_install_asr_model_subprocess_bootstrap,
    prepare_backend_import_path,
    reexec_into_venv_launcher,
    should_reexec_into_venv_python,
    use_inprocess_backend,
)
from desktop.runtime_bootstrap import DesktopRuntimePaths, detect_runtime_paths


class DesktopBackendHostTests(unittest.TestCase):
    def test_should_reexec_only_for_frozen_runtime_with_venv(self) -> None:
        os.environ.pop(VENV_LAUNCHER_REEXEC_ENV, None)
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            paths = DesktopRuntimePaths(
                project_root=tmp,
                bundle_root=tmp / "app-runtime",
                data_dir=tmp / "user-data",
                logs_dir=tmp / "logs",
                runtime_root=tmp / "runtime",
                cache_root=tmp / "runtime" / "cache",
                temp_root=tmp / "runtime" / "tmp",
                local_python=tmp / ".python" / "python.exe",
                venv_python=tmp / ".venv" / "Scripts" / "python.exe",
                install_profile_file=tmp / "user-data" / "install_profile.txt",
                torch_profile_state_file=tmp / ".venv" / "torch_profile_state.txt",
                bootstrap_script=tmp / "bootstrap-python.ps1",
                runtime_base_requirements=tmp / "requirements.runtime.base.txt",
                runtime_ai_requirements=tmp / "requirements.runtime.ai.txt",
                torch_cpu_requirements=tmp / "requirements.torch.cpu.txt",
                torch_cuda_requirements=tmp / "requirements.torch.cuda.txt",
                frontend_dir=tmp / "app-runtime" / "frontend",
                overlay_dir=tmp / "app-runtime" / "overlay",
                fonts_dir=tmp / "fonts",
            )
            paths.venv_python.parent.mkdir(parents=True, exist_ok=True)
            paths.venv_python.write_text("", encoding="utf-8")
            with patch.object(sys, "frozen", True, create=True):
                self.assertTrue(should_reexec_into_venv_python(paths))
            with patch.object(sys, "frozen", False, create=True):
                self.assertFalse(should_reexec_into_venv_python(paths))
            with patch.object(sys, "frozen", True, create=True):
                with patch.dict(os.environ, {VENV_LAUNCHER_REEXEC_ENV: "1"}, clear=False):
                    self.assertFalse(should_reexec_into_venv_python(paths))

    def test_use_subprocess_after_venv_handoff(self) -> None:
        with patch.dict(os.environ, {VENV_LAUNCHER_REEXEC_ENV: "1"}, clear=False):
            self.assertFalse(use_inprocess_backend())
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(VENV_LAUNCHER_REEXEC_ENV, None)
            with patch.object(sys, "frozen", False, create=True):
                self.assertTrue(use_inprocess_backend())
            with patch.object(sys, "frozen", True, create=True):
                self.assertFalse(use_inprocess_backend())

    def test_build_backend_subprocess_bootstrap_appends_bundle_path(self) -> None:
        code = build_backend_subprocess_bootstrap(Path("C:/bundle/app-runtime"))
        self.assertIn("sys.path.append('C:/bundle/app-runtime')", code)
        self.assertNotIn("sys.path.insert(0", code)

    def test_build_install_asr_model_subprocess_bootstrap_appends_bundle_path(self) -> None:
        code = build_install_asr_model_subprocess_bootstrap(Path("C:/bundle/app-runtime"))
        self.assertIn("sys.path.append('C:/bundle/app-runtime')", code)
        self.assertIn("backend.install_asr_model", code)
        self.assertIn("'--model', 'eu'", code)

    def test_prepare_backend_import_path_appends_after_venv_handoff(self) -> None:
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            bundle = tmp / "app-runtime"
            bundle.mkdir()
            with patch.dict(os.environ, {VENV_LAUNCHER_REEXEC_ENV: "1"}, clear=False):
                prepare_backend_import_path(bundle)
            self.assertEqual(sys.path[-1], str(bundle.resolve()))

    def test_reexec_spawns_venv_launcher_on_windows(self) -> None:
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            paths = DesktopRuntimePaths(
                project_root=tmp,
                bundle_root=tmp / "app-runtime",
                data_dir=tmp / "user-data",
                logs_dir=tmp / "logs",
                runtime_root=tmp / "runtime",
                cache_root=tmp / "runtime" / "cache",
                temp_root=tmp / "runtime" / "tmp",
                local_python=tmp / ".python" / "python.exe",
                venv_python=tmp / ".venv" / "Scripts" / "python.exe",
                install_profile_file=tmp / "user-data" / "install_profile.txt",
                torch_profile_state_file=tmp / ".venv" / "torch_profile_state.txt",
                bootstrap_script=tmp / "bootstrap-python.ps1",
                runtime_base_requirements=tmp / "requirements.runtime.base.txt",
                runtime_ai_requirements=tmp / "requirements.runtime.ai.txt",
                torch_cpu_requirements=tmp / "requirements.torch.cpu.txt",
                torch_cuda_requirements=tmp / "requirements.torch.cuda.txt",
                frontend_dir=tmp / "app-runtime" / "frontend",
                overlay_dir=tmp / "app-runtime" / "overlay",
                fonts_dir=tmp / "fonts",
            )
            paths.venv_python.parent.mkdir(parents=True, exist_ok=True)
            paths.venv_python.write_text("", encoding="utf-8")
            with patch.object(os, "name", "nt"):
                with patch("desktop.backend_host.subprocess.Popen") as popen:
                    with patch("desktop.backend_host.os._exit", side_effect=SystemExit(0)) as exit_:
                        with self.assertRaises(SystemExit):
                            reexec_into_venv_launcher(
                                paths,
                                handoff_env={"SST_HANDOFF_STARTUP_MODE": "local"},
                            )
                        popen.assert_called_once()
                        exit_.assert_called_once_with(0)
                        creationflags = popen.call_args.kwargs.get("creationflags", 0)
                        self.assertEqual(creationflags, _windows_handoff_creationflags())

    def test_detect_runtime_paths_honors_env_project_and_bundle_roots(self) -> None:
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            project = tmp / "install"
            bundle = tmp / "install" / "app-runtime"
            project.mkdir()
            bundle.mkdir()
            previous_project = os.environ.get("SST_PROJECT_ROOT")
            previous_bundle = os.environ.get("SST_BUNDLE_ROOT")
            os.environ["SST_PROJECT_ROOT"] = str(project)
            os.environ["SST_BUNDLE_ROOT"] = str(bundle)
            try:
                with patch.object(sys, "frozen", False, create=True):
                    paths = detect_runtime_paths()
            finally:
                if previous_project is None:
                    os.environ.pop("SST_PROJECT_ROOT", None)
                else:
                    os.environ["SST_PROJECT_ROOT"] = previous_project
                if previous_bundle is None:
                    os.environ.pop("SST_BUNDLE_ROOT", None)
                else:
                    os.environ["SST_BUNDLE_ROOT"] = previous_bundle
            self.assertEqual(paths.project_root, project.resolve())
            self.assertEqual(paths.bundle_root, bundle.resolve())


if __name__ == "__main__":
    unittest.main()
