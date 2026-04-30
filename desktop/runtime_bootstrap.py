from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


PYTHON_VERSION = "3.11.9"
DESKTOP_USER_DATA_DIRNAME = "user-data"
OFFLINE_SITE_PACKAGES_DIR = Path("vendor") / "python-site-packages"
OFFLINE_AI_SEED_PACKAGES = (
    "lightning",
    "lightning-2.4.0.dist-info",
)


@dataclass(frozen=True)
class DesktopRuntimePaths:
    project_root: Path
    bundle_root: Path
    data_dir: Path
    logs_dir: Path
    runtime_root: Path
    cache_root: Path
    temp_root: Path
    local_python: Path
    venv_python: Path
    install_profile_file: Path
    torch_profile_state_file: Path
    bootstrap_script: Path
    runtime_base_requirements: Path
    runtime_ai_requirements: Path
    torch_cpu_requirements: Path
    torch_cuda_requirements: Path
    frontend_dir: Path
    overlay_dir: Path
    fonts_dir: Path


def normalize_install_profile(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"cpu", "nvidia"} else None


def _project_runtime_root(project_root: Path) -> Path:
    explicit_root = os.environ.get("SST_RUNTIME_ROOT")
    if explicit_root:
        return Path(explicit_root).resolve()

    public_root = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    project_token = hashlib.sha1(str(project_root).encode("utf-8", errors="ignore")).hexdigest()[:10]
    return (public_root / "Documents" / "StreamSubtitleTranslatorRuntime" / f"{project_root.name}-{project_token}").resolve()


def detect_runtime_paths() -> DesktopRuntimePaths:
    source_root = Path(__file__).resolve().parent.parent
    bundle_root = Path(getattr(sys, "_MEIPASS", source_root)).resolve()
    is_frozen = bool(getattr(sys, "frozen", False))
    project_root = Path(sys.executable).resolve().parent if is_frozen else source_root
    data_dir = project_root / DESKTOP_USER_DATA_DIRNAME
    runtime_root = _project_runtime_root(project_root)
    return DesktopRuntimePaths(
        project_root=project_root,
        bundle_root=bundle_root,
        data_dir=data_dir,
        logs_dir=project_root / "logs",
        runtime_root=runtime_root,
        cache_root=runtime_root / "cache",
        temp_root=runtime_root / "tmp",
        local_python=project_root / ".python" / "python.exe",
        venv_python=project_root / ".venv" / "Scripts" / "python.exe",
        install_profile_file=data_dir / "install_profile.txt",
        torch_profile_state_file=project_root / ".venv" / "torch_profile_state.txt",
        bootstrap_script=bundle_root / "bootstrap-python.ps1",
        runtime_base_requirements=bundle_root / "requirements.runtime.base.txt",
        runtime_ai_requirements=bundle_root / "requirements.runtime.ai.txt",
        torch_cpu_requirements=bundle_root / "requirements.torch.cpu.txt",
        torch_cuda_requirements=bundle_root / "requirements.torch.cuda.txt",
        frontend_dir=bundle_root / "frontend",
        overlay_dir=bundle_root / "overlay",
        fonts_dir=project_root / "fonts",
    )


def auto_detect_install_profile() -> str:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return "cpu"
    try:
        completed = subprocess.run(
            [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return "cpu"
    if completed.returncode == 0 and (completed.stdout or "").strip():
        return "nvidia"
    return "cpu"


def _copy_if_missing(source: Path, destination: Path) -> None:
    if destination.exists() or not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _migrate_legacy_logs_dir(paths: DesktopRuntimePaths) -> None:
    legacy_logs_dir = paths.data_dir / "logs"
    target_logs_dir = paths.logs_dir
    if not legacy_logs_dir.exists() or legacy_logs_dir.resolve() == target_logs_dir.resolve():
        return
    target_logs_dir.mkdir(parents=True, exist_ok=True)
    for legacy_item in legacy_logs_dir.glob("*"):
        if not legacy_item.is_file():
            continue
        destination = target_logs_dir / legacy_item.name
        if destination.exists():
            continue
        _copy_if_missing(legacy_item, destination)
    try:
        legacy_logs_dir.rmdir()
    except OSError:
        pass


def ensure_runtime_layout(paths: DesktopRuntimePaths) -> None:
    cache_root = paths.cache_root
    huggingface_root = cache_root / "huggingface"
    required_directories = (
        paths.runtime_root,
        cache_root,
        cache_root / "pip",
        cache_root / "torch",
        cache_root / "matplotlib",
        cache_root / "numba",
        cache_root / "xdg",
        cache_root / "cuda",
        huggingface_root,
        huggingface_root / "hub",
        huggingface_root / "transformers",
        huggingface_root / "datasets",
        paths.temp_root,
        paths.data_dir,
        paths.data_dir / "profiles",
        paths.logs_dir,
        paths.data_dir / "exports",
        paths.data_dir / "cache",
        paths.data_dir / "models",
        paths.fonts_dir,
    )
    for directory in required_directories:
        directory.mkdir(parents=True, exist_ok=True)

    bundled_data_dir = paths.bundle_root / "backend" / "data"
    _copy_if_missing(bundled_data_dir / "config.example.json", paths.data_dir / "config.example.json")
    _copy_if_missing(
        bundled_data_dir / "dictionary_overrides.example.json",
        paths.data_dir / "dictionary_overrides.example.json",
    )
    _copy_if_missing(bundled_data_dir / "models" / "README.txt", paths.data_dir / "models" / "README.txt")

    bundled_fonts_dir = paths.bundle_root / "fonts"
    if bundled_fonts_dir.exists():
        for source_file in bundled_fonts_dir.rglob("*"):
            if not source_file.is_file():
                continue
            relative_path = source_file.relative_to(bundled_fonts_dir)
            _copy_if_missing(source_file, paths.fonts_dir / relative_path)
    _migrate_legacy_logs_dir(paths)


def build_runtime_environment(paths: DesktopRuntimePaths, *, pythonpath_root: Path | None = None) -> dict[str, str]:
    cache_root = paths.cache_root
    temp_root = paths.temp_root
    huggingface_root = cache_root / "huggingface"
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["PIP_CACHE_DIR"] = str(cache_root / "pip")
    env["HF_HOME"] = str(huggingface_root)
    env["HUGGINGFACE_HUB_CACHE"] = str(huggingface_root / "hub")
    env["TRANSFORMERS_CACHE"] = str(huggingface_root / "transformers")
    env["HF_DATASETS_CACHE"] = str(huggingface_root / "datasets")
    env["TORCH_HOME"] = str(cache_root / "torch")
    env["MPLCONFIGDIR"] = str(cache_root / "matplotlib")
    env["NUMBA_CACHE_DIR"] = str(cache_root / "numba")
    env["XDG_CACHE_HOME"] = str(cache_root / "xdg")
    env["CUDA_CACHE_PATH"] = str(cache_root / "cuda")
    env["TMP"] = str(temp_root)
    env["TEMP"] = str(temp_root)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["SST_PROJECT_ROOT"] = str(paths.project_root)
    env["SST_BUNDLE_ROOT"] = str(paths.bundle_root)
    if pythonpath_root is not None:
        env["SST_PYTHONPATH_ROOT"] = str(pythonpath_root)
    return env


class RuntimeBootstrapper:
    def __init__(
        self,
        *,
        paths: DesktopRuntimePaths,
        log: Callable[[str], None],
        status: Callable[[str], None],
        register_process: Callable[[subprocess.Popen[str]], None],
        unregister_process: Callable[[subprocess.Popen[str]], None],
    ) -> None:
        self._paths = paths
        self._log = log
        self._status = status
        self._register_process = register_process
        self._unregister_process = unregister_process

    def ensure_backend_environment(self, *, install_profile_override: str | None = None) -> tuple[Path, str]:
        python_exe = self.ensure_base_environment()
        install_profile = self.ensure_local_asr_runtime(install_profile_override=install_profile_override)
        return python_exe, install_profile

    def ensure_base_environment(self) -> Path:
        ensure_runtime_layout(self._paths)
        self._ensure_local_python()
        self._ensure_venv()
        self._ensure_pip_available()
        self._ensure_base_requirements()
        return self._paths.venv_python

    def ensure_local_asr_runtime(self, *, install_profile_override: str | None = None) -> str:
        ensure_runtime_layout(self._paths)
        self._ensure_local_python()
        self._ensure_venv()
        self._ensure_pip_available()
        self._ensure_base_requirements()
        install_profile = self._resolve_install_profile(install_profile_override)
        self._ensure_torch_profile(install_profile)
        self._ensure_ai_requirements()
        self._ensure_model_directory()
        return install_profile

    def runtime_environment(self) -> dict[str, str]:
        return build_runtime_environment(self._paths)

    def _validate_python(self, python_exe: Path) -> bool:
        if not python_exe.exists():
            return False
        try:
            completed = subprocess.run(
                [str(python_exe), "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            return False
        output = (completed.stdout or completed.stderr or "").strip()
        if completed.returncode != 0 or not output.lower().startswith("python "):
            return False
        try:
            _, version = output.split(" ", 1)
            major, minor, *_rest = version.strip().split(".")
        except ValueError:
            return False
        if major != "3":
            return False
        try:
            return int(minor) >= 10
        except ValueError:
            return False

    def _run_command(
        self,
        args: list[str],
        *,
        description: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        allow_failure: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        self._log(f"[cmd] {description}")
        process = subprocess.Popen(
            args,
            cwd=str(cwd or self._paths.project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._register_process(process)
        output_lines: list[str] = []
        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.rstrip()
                if not line:
                    continue
                output_lines.append(line)
                self._log(line)
            return_code = process.wait()
        finally:
            self._unregister_process(process)
        completed = subprocess.CompletedProcess(args=args, returncode=return_code, stdout="\n".join(output_lines), stderr=None)
        if return_code != 0 and not allow_failure:
            detail = output_lines[-1] if output_lines else f"Command failed with exit code {return_code}."
            raise RuntimeError(f"{description} failed. {detail}")
        return completed

    def _ensure_local_python(self) -> None:
        self._status("Resolving project-local Python runtime...")
        if self._validate_python(self._paths.local_python):
            self._log(f"[python] Reusing {self._paths.local_python}")
            return
        if not self._paths.bootstrap_script.exists():
            raise RuntimeError(f"Missing bootstrap script: {self._paths.bootstrap_script}")
        self._status("Provisioning local CPython runtime into .python ...")
        self._run_command(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self._paths.bootstrap_script),
                "-ProjectRoot",
                str(self._paths.project_root),
                "-PythonVersion",
                PYTHON_VERSION,
            ],
            description="bootstrap local Python runtime",
            cwd=self._paths.project_root,
            env=build_runtime_environment(self._paths, pythonpath_root=self._paths.project_root),
        )
        if not self._validate_python(self._paths.local_python):
            raise RuntimeError("Project-local Python provisioning finished, but .python\\python.exe is still not usable.")

    def _ensure_venv(self) -> None:
        self._status("Creating or validating .venv ...")
        if self._validate_python(self._paths.venv_python):
            self._log(f"[venv] Reusing {self._paths.venv_python}")
            return
        venv_root = self._paths.project_root / ".venv"
        if venv_root.exists():
            self._log("[venv] Existing .venv is invalid. Recreating it.")
            shutil.rmtree(venv_root, ignore_errors=True)
        self._run_command(
            [str(self._paths.local_python), "-m", "venv", str(venv_root)],
            description="create local virtual environment",
            cwd=self._paths.project_root,
            env=build_runtime_environment(self._paths, pythonpath_root=self._paths.project_root),
        )
        if not self._validate_python(self._paths.venv_python):
            raise RuntimeError("Virtual environment creation finished, but .venv\\Scripts\\python.exe is not usable.")

    def _resolve_install_profile(self, install_profile_override: str | None = None) -> str:
        self._status("Resolving local ASR install profile...")
        override = normalize_install_profile(install_profile_override)
        if override:
            self._paths.install_profile_file.parent.mkdir(parents=True, exist_ok=True)
            self._paths.install_profile_file.write_text(override, encoding="utf-8")
            self._log(f"[profile] Using launcher-selected install profile: {override}")
            return override
        if self._paths.install_profile_file.exists():
            try:
                value = self._paths.install_profile_file.read_text(encoding="utf-8").strip().lower()
            except OSError:
                value = ""
            if normalize_install_profile(value):
                self._log(f"[profile] Reusing saved install profile: {value}")
                return value

        profile = self._auto_detect_install_profile()
        self._paths.install_profile_file.parent.mkdir(parents=True, exist_ok=True)
        self._paths.install_profile_file.write_text(profile, encoding="utf-8")
        self._log(f"[profile] Saved auto-detected install profile: {profile}")
        return profile

    def _auto_detect_install_profile(self) -> str:
        profile = auto_detect_install_profile()
        if profile == "nvidia":
            self._log("[profile] Detected NVIDIA GPU. Defaulting to NVIDIA profile.")
        else:
            self._log("[profile] NVIDIA GPU was not confirmed. Defaulting to CPU-only profile.")
        return profile

    def _ensure_pip_available(self) -> None:
        self._status("Updating pip in the local environment...")
        self._run_command(
            [str(self._paths.venv_python), "-m", "pip", "install", "--upgrade", "pip"],
            description="upgrade pip",
            env=build_runtime_environment(self._paths),
        )

    def _torch_runtime_matches_profile(self, install_profile: str) -> bool:
        completed = self._run_command(
            [
                str(self._paths.venv_python),
                "-c",
                (
                    "import sys, torch, torchaudio; "
                    "build = getattr(getattr(torch, 'version', None), 'cuda', None); "
                    "audio_ver = getattr(torchaudio, '__version__', ''); "
                    f"profile = {json.dumps(install_profile)}; "
                    "ok_cpu = (not build) and ('+cu' not in audio_ver); "
                    "ok_nvidia = bool(build) and ('+cu' in audio_ver); "
                    "ok = ok_cpu if profile == 'cpu' else ok_nvidia; "
                    "raise SystemExit(0 if ok else 1)"
                ),
            ],
            description="validate existing torch profile",
            env=build_runtime_environment(self._paths),
            allow_failure=True,
        )
        return completed.returncode == 0

    def _torch_profile_matches(self, install_profile: str) -> bool:
        if not self._paths.torch_profile_state_file.exists():
            return False
        try:
            marker = self._paths.torch_profile_state_file.read_text(encoding="utf-8").strip().lower()
        except OSError:
            return False
        if marker != install_profile:
            return False
        return self._torch_runtime_matches_profile(install_profile)

    def _ensure_torch_profile(self, install_profile: str) -> None:
        if self._torch_profile_matches(install_profile):
            self._log(f"[torch] Reusing existing {install_profile} PyTorch runtime.")
            return
        self._status("Installing the local PyTorch runtime...")
        self._run_command(
            [str(self._paths.venv_python), "-m", "pip", "uninstall", "-y", "torch", "torchaudio"],
            description="remove previous torch runtime",
            env=build_runtime_environment(self._paths),
            allow_failure=True,
        )
        requirements_path = self._paths.torch_cpu_requirements if install_profile == "cpu" else self._paths.torch_cuda_requirements
        if not requirements_path.exists():
            raise RuntimeError(f"Missing torch requirements file: {requirements_path}")
        profile_label = "CPU-only" if install_profile == "cpu" else "NVIDIA CUDA 12.8"
        self._run_command(
            [str(self._paths.venv_python), "-m", "pip", "install", "--upgrade", "-r", str(requirements_path)],
            description=f"install {profile_label} PyTorch runtime",
            env=build_runtime_environment(self._paths),
        )
        if not self._torch_runtime_matches_profile(install_profile):
            self._paths.torch_profile_state_file.unlink(missing_ok=True)
            raise RuntimeError(
                f"{profile_label} PyTorch runtime finished installing, but torch/torchaudio are still not importable."
            )
        self._paths.torch_profile_state_file.write_text(install_profile, encoding="utf-8")

    def _base_requirements_satisfied(self) -> bool:
        completed = self._run_command(
            [
                str(self._paths.venv_python),
                "-c",
                "import fastapi, uvicorn, pydantic, websockets, sounddevice, numpy, httpx, webrtcvad",
            ],
            description="validate base desktop Python requirements",
            env=build_runtime_environment(self._paths),
            allow_failure=True,
        )
        return completed.returncode == 0

    def _ensure_base_requirements(self) -> None:
        if self._base_requirements_satisfied():
            self._log("[deps] Base desktop Python requirements are already available.")
            return
        if not self._paths.runtime_base_requirements.exists():
            raise RuntimeError(f"Missing requirements file: {self._paths.runtime_base_requirements}")
        self._status("Installing base desktop dependencies...")
        self._run_command(
            [str(self._paths.venv_python), "-m", "pip", "install", "-r", str(self._paths.runtime_base_requirements)],
            description="install base desktop Python requirements",
            env=build_runtime_environment(self._paths),
        )

    def _ai_requirements_satisfied(self) -> bool:
        completed = self._run_command(
            [
                str(self._paths.venv_python),
                "-c",
                "import importlib; importlib.import_module('nemo.collections.asr.models')",
            ],
            description="validate local AI recognition requirements",
            env=build_runtime_environment(self._paths),
            allow_failure=True,
        )
        return completed.returncode == 0

    def _ensure_ai_requirements(self) -> None:
        if self._ai_requirements_satisfied():
            self._log("[deps] Local AI recognition requirements are already available.")
            return
        if not self._paths.runtime_ai_requirements.exists():
            raise RuntimeError(f"Missing requirements file: {self._paths.runtime_ai_requirements}")
        self._seed_offline_ai_packages()
        self._status("Installing local AI recognition dependencies...")
        self._run_command(
            [str(self._paths.venv_python), "-m", "pip", "install", "-r", str(self._paths.runtime_ai_requirements)],
            description="install local AI recognition requirements",
            env=build_runtime_environment(self._paths),
        )

    def _seed_offline_ai_packages(self) -> None:
        vendor_root = self._paths.bundle_root / OFFLINE_SITE_PACKAGES_DIR
        if not vendor_root.exists():
            self._log(f"[deps] No offline AI seed package directory found at {vendor_root}")
            return

        target_site_packages = self._paths.venv_python.parent.parent / "Lib" / "site-packages"
        target_site_packages.mkdir(parents=True, exist_ok=True)
        copied_any = False
        for package_name in OFFLINE_AI_SEED_PACKAGES:
            source_path = vendor_root / package_name
            if not source_path.exists():
                self._log(f"[deps] Offline AI seed package missing from bundle: {source_path}")
                continue
            destination_path = target_site_packages / package_name
            if destination_path.exists():
                continue
            if source_path.is_dir():
                shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
            else:
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination_path)
            copied_any = True
            self._log(f"[deps] Seeded offline AI package: {package_name}")

        if copied_any:
            self._log("[deps] Offline AI seed packages were copied into the local .venv before NeMo install.")

    def _ensure_model_directory(self) -> None:
        model_dir = self._paths.data_dir / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_file = model_dir / "parakeet-tdt-0.6b-v3" / "parakeet-tdt-0.6b-v3.nemo"
        if model_file.exists():
            self._log(f"[model] Reusing local model file: {model_file}")
            return
        self._log("[model] Official Parakeet model is not installed yet. The first runtime start will download it locally.")

    def cleanup_transient_runtime_files(self, *, preserve_paths: list[Path] | None = None) -> None:
        pip_cache_dir = self._paths.cache_root / "pip"
        temp_root = self._paths.temp_root
        preserved = {path.resolve() for path in (preserve_paths or [])}
        for path in (pip_cache_dir, temp_root):
            if not path.exists():
                continue
            try:
                resolved_path = path.resolve()
                if resolved_path in preserved:
                    continue
                if path.is_dir():
                    if preserved and resolved_path == temp_root.resolve():
                        removed_children = 0
                        for child in path.iterdir():
                            child_resolved = child.resolve()
                            if child_resolved in preserved:
                                continue
                            if any(parent == child_resolved or parent.is_relative_to(child_resolved) for parent in preserved):
                                continue
                            if child.is_dir():
                                shutil.rmtree(child, ignore_errors=True)
                            else:
                                child.unlink(missing_ok=True)
                            removed_children += 1
                        if removed_children:
                            self._log(f"[cleanup] Removed transient runtime entries from: {path}")
                        continue
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)
                self._log(f"[cleanup] Removed transient runtime path: {path}")
            except Exception as exc:
                self._log(f"[cleanup] Skipped transient runtime cleanup for {path}: {exc}")
