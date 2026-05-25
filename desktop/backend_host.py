from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from desktop.runtime_bootstrap import DesktopRuntimePaths, build_runtime_environment
from desktop.subprocess_trace import logged_popen, subprocess_trace

VENV_LAUNCHER_REEXEC_ENV = "SST_VENV_LAUNCHER_REEXEC"


def _windows_handoff_creationflags() -> int:
    return (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )


def should_reexec_into_venv_python(paths: DesktopRuntimePaths) -> bool:
    if os.environ.get(VENV_LAUNCHER_REEXEC_ENV, "").strip() == "1":
        return False
    if not getattr(sys, "frozen", False):
        return False
    return paths.venv_python.is_file()


def reexec_into_venv_launcher(
    paths: DesktopRuntimePaths,
    *,
    launcher_argv: list[str] | None = None,
    handoff_env: dict[str, str] | None = None,
) -> None:
    """
    Replace the frozen managed-runtime process with the project venv interpreter.

    Reserved for manual/legacy use. The desktop launcher keeps a single pywebview window
    and starts ASR via a venv ``backend.run`` subprocess instead of reexecing itself.
    """
    env = build_runtime_environment(paths)
    env[VENV_LAUNCHER_REEXEC_ENV] = "1"
    env["SST_PROJECT_ROOT"] = str(paths.project_root)
    env["SST_BUNDLE_ROOT"] = str(paths.bundle_root)
    if handoff_env:
        env.update({str(key): str(value) for key, value in handoff_env.items()})
    if launcher_argv:
        env["SST_LAUNCHER_ARGV"] = " ".join(launcher_argv)

    bundle_root = paths.bundle_root.as_posix()
    bootstrap_code = (
        "import runpy, sys; "
        f"sys.path.append({bundle_root!r}); "
        "runpy.run_module('desktop.launcher', run_name='__main__')"
    )
    args = [str(paths.venv_python), "-u", "-c", bootstrap_code]
    if launcher_argv:
        args.extend(launcher_argv)

    if os.name == "nt":
        # PyInstaller frozen EXE -> external venv python via execve is unreliable on Windows.
        subprocess_trace("desktop", "venv_handoff_spawn", launcher_argv=launcher_argv or [])
        logged_popen(
            "venv_handoff",
            args,
            cwd=str(paths.project_root),
            env=env,
            creationflags=_windows_handoff_creationflags(),
            watch_exit=False,
            description="reexec desktop.launcher in project venv",
        )
        os._exit(0)
        return

    os.execve(str(paths.venv_python), args, env)


def use_inprocess_backend() -> bool:
    """Desktop backend hosting mode.

    After venv handoff the launcher must not run uvicorn in a background thread inside the
    pywebview process: on Windows, PortAudio capture from that thread often delivers no real
    microphone frames while the pipeline still looks alive.

    Default after handoff: subprocess via the same ``.venv\\Scripts\\python.exe`` as start.bat.
  """
    if os.environ.get(VENV_LAUNCHER_REEXEC_ENV, "").strip() == "1":
        return False
    if os.environ.get("SST_DESKTOP_BACKEND_INPROC", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return not getattr(sys, "frozen", False)


def apply_backend_process_environment(env: dict[str, str]) -> None:
    for key, value in env.items():
        os.environ[str(key)] = str(value)


def prepare_backend_import_path(bundle_root: Path) -> None:
    bundle_text = str(bundle_root.resolve())
    if bundle_text in sys.path:
        return
    if os.environ.get(VENV_LAUNCHER_REEXEC_ENV, "").strip() == "1":
        sys.path.append(bundle_text)
        return
    sys.path.insert(0, bundle_text)


def build_backend_subprocess_bootstrap(bundle_root: Path) -> str:
    bundle_posix = bundle_root.as_posix()
    return (
        "import runpy, sys; "
        f"sys.path.append({bundle_posix!r}); "
        "runpy.run_module('backend.run', run_name='__main__')"
    )


def build_install_asr_model_subprocess_bootstrap(bundle_root: Path, *, model: str = "eu") -> str:
    """Run ``backend.install_asr_model`` from the project venv with ``app-runtime`` on ``sys.path``."""
    bundle_posix = bundle_root.as_posix()
    model_literal = repr(str(model))
    return (
        "import runpy, sys; "
        f"sys.path.append({bundle_posix!r}); "
        f"sys.argv = ['install_asr_model', '--model', {model_literal}]; "
        "runpy.run_module('backend.install_asr_model', run_name='__main__')"
    )


def start_inprocess_backend(
    *,
    bundle_root: Path,
    env: dict[str, str],
    host: str,
    port: int,
    remote_role: str,
    allow_lan: bool,
) -> Any:
    apply_backend_process_environment(env)
    prepare_backend_import_path(bundle_root)
    os.environ["SST_REMOTE_ROLE"] = remote_role
    os.environ["SST_ALLOW_LAN"] = "1" if allow_lan else "0"

    # Dynamic import keeps PyInstaller from embedding torch/NeMo into app-runtime.
    import importlib

    app = importlib.import_module("backend.app").app
    settings = importlib.import_module("backend.config").settings
    LocalServerThread = importlib.import_module("backend.server_runtime").LocalServerThread

    bind_host = "0.0.0.0" if allow_lan else host
    settings.app_host = bind_host
    settings.app_port = int(port)
    server = LocalServerThread(app=app, host=bind_host, port=port, log_level="warning")
    server.start()
    if server.startup_error is not None:
        raise RuntimeError(f"Local backend thread failed to start: {server.startup_error}") from server.startup_error
    return server
