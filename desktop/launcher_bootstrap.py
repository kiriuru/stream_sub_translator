from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import traceback
import webbrowser
import winreg
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.error import URLError
from urllib.request import Request, urlopen

from desktop.backend_host import (
    VENV_LAUNCHER_REEXEC_ENV,
    build_backend_subprocess_bootstrap,
    reexec_into_venv_launcher,
    should_reexec_into_venv_python,
    start_inprocess_backend,
    use_inprocess_backend,
)
from backend.core.diagnostic_flags import (
    is_api_trace_enabled,
    is_startup_journey_enabled,
    is_ui_trace_enabled,
)
from backend.core.startup_journey_log import (
    collect_runtime_environment_snapshot,
    configure_startup_journey_log,
    journey_log,
    journey_log_mapping,
)
from backend.core.api_trace_log import configure_api_trace_log
from backend.core.ui_trace_log import configure_ui_trace_log, ui_trace
from backend.config.defaults import build_default_config
from desktop.asr_config_repair import repair_legacy_custom_asr_realtime
from desktop.runtime_bootstrap import (
    RuntimeBootstrapper,
    auto_detect_install_profile,
    detect_runtime_paths,
    normalize_install_profile,
)
from desktop.subprocess_trace import (
    configure_subprocess_trace,
    log_subprocess_terminate,
    logged_popen,
    subprocess_trace,
)
from desktop.splash_screen import build_splash_html

from desktop import launcher_context
from desktop import launcher_api
from desktop.launcher_api import DesktopApi

for _export_name in dir(launcher_context):
    if _export_name.startswith("__"):
        continue
    globals()[_export_name] = getattr(launcher_context, _export_name)
for _export_name in dir(launcher_api):
    if _export_name.startswith("__") or _export_name == "DesktopApi":
        continue
    globals()[_export_name] = getattr(launcher_api, _export_name)

from desktop.browser_worker_launcher import BrowserWorkerLauncherMixin
from desktop.launcher_backend import LauncherBackendMixin
from desktop.launcher_window import LauncherWindowMixin

class DesktopLauncher(BrowserWorkerLauncherMixin, LauncherWindowMixin, LauncherBackendMixin):
    def __init__(self, *, debug_webview: bool = False, web_speech_only: bool = False) -> None:
        self._paths = detect_runtime_paths()
        self._debug_webview = debug_webview
        self._web_speech_only = bool(web_speech_only)
        self._log_path = self._paths.logs_dir / "desktop-launcher.log"
        self._legacy_log_path = self._paths.project_root / ".tmp" / "desktop-launcher.log"
        self._migrate_legacy_logs_dir()
        self._ensure_launcher_log_files()
        self._shutdown_started = threading.Event()
        self._startup_error_message: str | None = None
        self._child_processes: set[subprocess.Popen[str]] = set()
        self._child_process_lock = threading.Lock()
        self._backend_process: subprocess.Popen[str] | None = None
        self._backend_server: Any | None = None
        self._backend_tail: deque[str] = deque(maxlen=80)
        self._backend_output_thread: threading.Thread | None = None
        self._runtime_metrics_monitor_thread: threading.Thread | None = None
        self._launch_option_event = threading.Event()
        self._selected_launch_option: str | None = None
        self._selected_launch_option_lock = threading.Lock()
        self._browser_worker_last_error: str | None = None
        self._main_window: Any | None = None
        self._splash_shell_active = True
        self._dashboard_resize_done = False
        self._dashboard_navigation_started = False
        self._context = self._build_context()
        self._write_log("launcher initialized")

    def _migrate_legacy_logs_dir(self) -> None:
        legacy_logs_dir = self._paths.data_dir / "logs"
        target_logs_dir = self._paths.logs_dir
        if not legacy_logs_dir.exists() or legacy_logs_dir.resolve() == target_logs_dir.resolve():
            return
        target_logs_dir.mkdir(parents=True, exist_ok=True)
        for legacy_item in legacy_logs_dir.glob("*"):
            if not legacy_item.is_file():
                continue
            destination = target_logs_dir / legacy_item.name
            if destination.exists():
                legacy_item.unlink(missing_ok=True)
                continue
            os.replace(legacy_item, destination)
        try:
            legacy_logs_dir.rmdir()
        except OSError:
            pass

    _LEGACY_EMPTY_CHANNEL_LOG_STEMS = (
        "dashboard-live-events",
        "overlay-events",
        "browser-recognition",
    )

    def _ensure_launcher_log_files(self) -> None:
        log_dir = self._paths.logs_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        if is_ui_trace_enabled():
            configure_ui_trace_log(log_dir)
        if is_api_trace_enabled():
            configure_api_trace_log(log_dir)
        if self._legacy_log_path.exists():
            try:
                self._legacy_log_path.unlink()
            except OSError:
                pass
        self._rotate_log_file(self._log_path)
        self._remove_empty_legacy_channel_logs(log_dir)

    @staticmethod
    def _remove_empty_legacy_channel_logs(log_dir: Path) -> None:
        """Drop obsolete zero-byte channel logs; live client events use session-latest.jsonl."""
        for stem in DesktopLauncher._LEGACY_EMPTY_CHANNEL_LOG_STEMS:
            for suffix in (".log", ".old.log"):
                path = log_dir / f"{stem}{suffix}"
                if not path.exists():
                    continue
                try:
                    if path.stat().st_size == 0:
                        path.unlink()
                except OSError:
                    pass

    @staticmethod
    def _rotate_log_file(log_path: Path) -> None:
        """Preserve the previous run's log next to the live one for triage."""
        log_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path = log_path.with_name(f"{log_path.stem}.old{log_path.suffix}")
        if log_path.exists():
            try:
                if archive_path.exists():
                    archive_path.unlink()
                os.replace(log_path, archive_path)
            except OSError:
                pass
        try:
            log_path.write_text("", encoding="utf-8")
        except OSError:
            pass

    def _build_context(self) -> LaunchContext:
        base_url = f"http://{APP_HOST}:{APP_PORT}"
        cfg_path = self._paths.data_dir / "config.json"
        worker_browser = _load_worker_launch_browser_preference(cfg_path)
        browser_worker_path = _classic_browser_worker_path_for_preference(worker_browser)
        return LaunchContext(
            desktop_mode=True,
            base_url=base_url,
            dashboard_url=f"{base_url}/?desktop=1",
            overlay_url=f"{base_url}/overlay",
            browser_worker_url=f"{base_url}{browser_worker_path}",
            worker_launch_browser=worker_browser,
            startup_mode=_load_saved_asr_mode(self._paths.data_dir / "config.json"),
            web_speech_only=self._web_speech_only,
            install_profile=_read_install_profile(self._paths.install_profile_file),
            remote_role="disabled",
            profile_name=_load_profile_name(self._paths.data_dir / "config.json"),
            project_root=str(self._paths.project_root),
            data_dir=str(self._paths.data_dir),
        )

    def _write_log(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        line = f"[{timestamp}] {message}\n"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _log_launch_context(self, *, python_exe: Path, env: dict[str, str]) -> None:
        context = self._context
        safe_env_keys = (
            "SST_PROJECT_ROOT",
            "SST_BUNDLE_ROOT",
            "SST_PYTHONPATH_ROOT",
            "SST_REMOTE_ROLE",
            "SST_ALLOW_LAN",
            "SST_DESKTOP_LAUNCHER",
            "SST_PYTHON_EXECUTABLE",
            "PYTHONUNBUFFERED",
        )
        env_summary = {key: env.get(key, "") for key in safe_env_keys if env.get(key)}
        self._write_log(
            "[launch-context] "
            + json.dumps(
                {
                    **asdict(context),
                    "python_exe": str(python_exe),
                    "venv_python": str(self._paths.venv_python),
                    "bundle_root": str(self._paths.bundle_root),
                    "runtime_root": str(self._paths.runtime_root),
                    "env": env_summary,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    def _set_launch_option(self, selection: str) -> bool:
        normalized = str(selection or "").strip().lower()
        if normalized not in {
            LAUNCH_OPTION_BROWSER,
            LAUNCH_OPTION_NVIDIA,
            LAUNCH_OPTION_CPU,
            LAUNCH_OPTION_REMOTE_CONTROLLER,
            LAUNCH_OPTION_REMOTE_WORKER,
        }:
            return False
        with self._selected_launch_option_lock:
            self._selected_launch_option = normalized
        self._launch_option_event.set()
        self._write_log(f"launcher startup option selected: {normalized}")
        journey_log("desktop", "launch_option_selected", selection=normalized)
        ui_trace("desktop", "splash", "launch_option_selected", selection=normalized)
        return True

    def _selected_launch_mode(self) -> str | None:
        with self._selected_launch_option_lock:
            return self._selected_launch_option

    def _publish_profile_prompt(
        self,
        window: Any,
        *,
        selected: str,
        saved_profile: str | None,
        detected_profile: str,
        saved_asr_mode: str,
    ) -> None:
        locale = self._current_ui_language()
        hint = _splash_profile_hint(
            locale,
            selected=selected,
            saved_profile=saved_profile,
            detected_profile=detected_profile,
            saved_asr_mode=saved_asr_mode,
        )
        payload = {"selected": selected, "hint": hint, "locked": False}
        try:
            window.evaluate_js(
                f"window.__sstSetLaunchOptionPrompt && window.__sstSetLaunchOptionPrompt({json.dumps(payload)});"
            )
        except Exception:
            pass

    def _consume_launch_handoff(self) -> tuple[str, str | None, str, bool] | None:
        startup_mode = str(os.environ.get("SST_HANDOFF_STARTUP_MODE", "") or "").strip()
        if not startup_mode:
            return None
        install_profile = normalize_install_profile(os.environ.get("SST_HANDOFF_INSTALL_PROFILE"))
        remote_role = str(os.environ.get("SST_HANDOFF_REMOTE_ROLE", "disabled") or "disabled").strip().lower()
        if remote_role not in {"disabled", "controller", "worker"}:
            remote_role = "disabled"
        allow_lan = str(os.environ.get("SST_HANDOFF_ALLOW_LAN", "") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        for key in (
            "SST_HANDOFF_STARTUP_MODE",
            "SST_HANDOFF_INSTALL_PROFILE",
            "SST_HANDOFF_REMOTE_ROLE",
            "SST_HANDOFF_ALLOW_LAN",
        ):
            os.environ.pop(key, None)
        return startup_mode, install_profile, remote_role, allow_lan

    def _needs_venv_python_handoff(self, startup_mode: str, remote_role: str) -> bool:
        if startup_mode != STARTUP_MODE_LOCAL:
            return False
        if remote_role not in {"disabled", "worker"}:
            return False
        return should_reexec_into_venv_python(self._paths)

    def _reexec_into_venv_python_for_local_asr(
        self,
        window: Any,
        *,
        startup_mode: str,
        install_profile: str | None,
        remote_role: str,
        allow_lan: bool,
    ) -> None:
        bootstrapper = RuntimeBootstrapper(
            paths=self._paths,
            log=lambda message: self._publish_window_log(window, message),
            status=lambda message: self._publish_window_status(window, message),
            register_process=self._register_child_process,
            unregister_process=self._unregister_child_process,
        )
        bootstrapper.ensure_desktop_shell_requirements()
        self._publish_window_log(
            window,
            "Handing off to project venv Python so microphone capture and backend share one process.",
        )
        reexec_into_venv_launcher(
            self._paths,
            launcher_argv=self._launcher_cli_argv(),
            handoff_env={
                "SST_HANDOFF_STARTUP_MODE": startup_mode,
                "SST_HANDOFF_INSTALL_PROFILE": install_profile or "",
                "SST_HANDOFF_REMOTE_ROLE": remote_role,
                "SST_HANDOFF_ALLOW_LAN": "1" if allow_lan else "0",
            },
        )

    def _try_immediate_venv_handoff_from_saved_local_profile(self) -> None:
        if not should_reexec_into_venv_python(self._paths):
            return
        if self._web_speech_only:
            return
        config_path = self._paths.data_dir / "config.json"
        if _load_saved_asr_mode(config_path) != STARTUP_MODE_LOCAL:
            return
        remote_role, allow_lan = _load_saved_remote_startup(config_path)
        if remote_role == "controller":
            return
        saved_profile = normalize_install_profile(_read_install_profile(self._paths.install_profile_file))
        if saved_profile in {LAUNCH_OPTION_CPU, LAUNCH_OPTION_NVIDIA}:
            install_profile = saved_profile
        elif remote_role == "worker":
            install_profile = auto_detect_install_profile()
        else:
            return
        if install_profile not in {LAUNCH_OPTION_CPU, LAUNCH_OPTION_NVIDIA}:
            return
        self._write_log(
            "immediate venv Python handoff for saved local ASR profile "
            f"({install_profile}, remote_role={remote_role})"
        )
        reexec_into_venv_launcher(
            self._paths,
            launcher_argv=self._launcher_cli_argv(),
            handoff_env={
                "SST_HANDOFF_STARTUP_MODE": STARTUP_MODE_LOCAL,
                "SST_HANDOFF_INSTALL_PROFILE": install_profile or "",
                "SST_HANDOFF_REMOTE_ROLE": remote_role,
                "SST_HANDOFF_ALLOW_LAN": "1" if allow_lan else "0",
            },
        )

    def _wait_for_launch_option_selection(self, window: Any) -> tuple[str, str | None, str, bool]:
        saved_profile = normalize_install_profile(_read_install_profile(self._paths.install_profile_file))
        detected_profile = auto_detect_install_profile()
        saved_asr_mode = _load_saved_asr_mode(self._paths.data_dir / "config.json")
        if self._web_speech_only:
            fallback_install_profile = saved_profile or detected_profile
            self._publish_window_status(window, status_key="launcher.status.preparing_browser")
            self._publish_window_log(
                window,
                "web-speech-only desktop build: auto-selecting Browser Speech quick start",
            )
            return STARTUP_MODE_BROWSER, fallback_install_profile, "disabled", False
        handoff = self._consume_launch_handoff()
        if handoff is not None:
            self._publish_window_log(window, "resuming startup after venv Python handoff")
            journey_log_mapping(
                "desktop",
                "launch_handoff_resume",
                {
                    "startup_mode": handoff[0],
                    "install_profile": handoff[1],
                    "remote_role": handoff[2],
                    "allow_lan": handoff[3],
                },
            )
            return handoff
        selected = LAUNCH_OPTION_BROWSER if saved_asr_mode == STARTUP_MODE_BROWSER else (saved_profile or detected_profile)
        self._launch_option_event.clear()
        with self._selected_launch_option_lock:
            self._selected_launch_option = None
        self._publish_profile_prompt(
            window,
            selected=selected,
            saved_profile=saved_profile,
            detected_profile=detected_profile,
            saved_asr_mode=saved_asr_mode,
        )
        self._publish_window_status(window, status_key="launcher.status.initial")
        self._publish_window_log(
            window,
            f"launch selector ready: saved_mode={saved_asr_mode}, saved_install={saved_profile or 'none'}, detected={detected_profile}, selected={selected}",
        )
        while not self._launch_option_event.wait(timeout=0.2):
            if self._shutdown_started.is_set():
                self._write_log("startup mode selection cancelled: desktop window closed before a choice was made")
                raise LaunchSelectionCancelled()
        chosen = self._selected_launch_mode() or selected
        if chosen == LAUNCH_OPTION_BROWSER:
            fallback_install_profile = saved_profile or detected_profile
            self._publish_window_status(window, status_key="launcher.status.preparing_browser")
            return STARTUP_MODE_BROWSER, fallback_install_profile, "disabled", False
        if chosen == LAUNCH_OPTION_REMOTE_CONTROLLER:
            self._publish_window_status(window, status_key="launcher.status.preparing_remote_controller")
            return STARTUP_MODE_LOCAL, None, "controller", False
        if chosen == LAUNCH_OPTION_REMOTE_WORKER:
            effective_profile = saved_profile or detected_profile
            locale = self._current_ui_language()
            worker_profile_label = "NVIDIA GPU" if effective_profile == "nvidia" else "CPU-only"
            self._publish_window_status(
                window,
                _splash_t(locale, "launcher.status.preparing_remote_worker", profile=worker_profile_label),
            )
            return STARTUP_MODE_LOCAL, effective_profile, "worker", True
        self._publish_window_status(
            window,
            status_key="launcher.status.preparing_nvidia"
            if chosen == LAUNCH_OPTION_NVIDIA
            else "launcher.status.preparing_cpu",
        )
        return STARTUP_MODE_LOCAL, chosen, "disabled", False

    def _apply_startup_mode_to_config(
        self,
        startup_mode: str,
        install_profile: str | None,
        *,
        remote_role: str = "disabled",
        allow_lan: bool = False,
    ) -> None:
        config_path = self._paths.data_dir / "config.json"
        prefer_gpu = install_profile == LAUNCH_OPTION_NVIDIA
        payload: dict[str, Any]
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text(encoding="utf-8"))
                payload = existing if isinstance(existing, dict) else {}
            except Exception:
                payload = {}
        else:
            payload = {}
        if not payload or not isinstance(payload.get("asr"), dict):
            payload = build_default_config(prefer_gpu_default=prefer_gpu)
        asr = payload.get("asr", {})
        if not isinstance(asr, dict):
            asr = {}
        if self._web_speech_only or startup_mode == STARTUP_MODE_BROWSER:
            asr["mode"] = STARTUP_MODE_BROWSER
            asr["desktop_profile_lock"] = DESKTOP_PROFILE_LOCK_BROWSER_SPEECH
        else:
            asr["mode"] = STARTUP_MODE_LOCAL
            asr.pop("desktop_profile_lock", None)
        if startup_mode == STARTUP_MODE_LOCAL and install_profile in {LAUNCH_OPTION_CPU, LAUNCH_OPTION_NVIDIA}:
            asr["prefer_gpu"] = install_profile == LAUNCH_OPTION_NVIDIA
        payload["asr"] = asr
        remote = payload.get("remote", {})
        if not isinstance(remote, dict):
            remote = {}
        lan = remote.get("lan", {})
        if not isinstance(lan, dict):
            lan = {}
        normalized_remote_role = str(remote_role or "disabled").strip().lower()
        if normalized_remote_role not in {"disabled", "controller", "worker"}:
            normalized_remote_role = "disabled"
        remote["enabled"] = normalized_remote_role != "disabled"
        remote["role"] = normalized_remote_role
        lan["bind_enabled"] = bool(allow_lan)
        remote["lan"] = lan
        payload["remote"] = remote
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_log(
            f"startup config applied: mode={asr.get('mode')} install_profile={install_profile or 'none'} remote_role={normalized_remote_role} allow_lan={allow_lan} -> {config_path}"
        )

    def bootstrap(self, window: Any) -> None:
        try:
            from desktop.deps_install_trace import configure_deps_install_trace

            # Deep traces (startup-journey, ui-trace, api-trace) are opt-in via
            # SST_DEEP_DIAGNOSTICS / SST_TRACE_* тАФ keep desktop launcher in sync
            # with the backend gate (`backend/core/app_bootstrap.py`) so the same
            # files are produced (or skipped) regardless of whether the user
            # started via start.bat or the desktop launcher.
            if is_startup_journey_enabled():
                configure_startup_journey_log(self._paths.project_root / "logs")
            # deps-install-trace and subprocess-trace stay always-on (small, bootstrap triage).
            configure_deps_install_trace(self._paths.logs_dir)
            configure_subprocess_trace(self._paths.logs_dir, text_log=self._write_log)
            if is_ui_trace_enabled():
                configure_ui_trace_log(self._paths.logs_dir)
            if is_api_trace_enabled():
                configure_api_trace_log(self._paths.logs_dir)
            journey_log_mapping(
                "desktop",
                "bootstrap_begin",
                {
                    "web_speech_only": self._web_speech_only,
                    "bundle_root": str(self._paths.bundle_root),
                    "project_root": str(self._paths.project_root),
                    **collect_runtime_environment_snapshot(),
                },
            )
            self._publish_window_log(window, "preflight started")
            if _is_port_in_use(APP_HOST, APP_PORT):
                raise RuntimeError(self._format_port_error())
            self._publish_window_log(window, "preflight passed")

            startup_mode, install_profile_override, remote_role, allow_lan = self._wait_for_launch_option_selection(
                window
            )
            journey_log_mapping(
                "desktop",
                "launch_option_resolved",
                {
                    "startup_mode": startup_mode,
                    "install_profile": install_profile_override,
                    "remote_role": remote_role,
                    "allow_lan": allow_lan,
                },
            )
            config_path = self._paths.data_dir / "config.json"
            if repair_legacy_custom_asr_realtime(config_path):
                self._publish_window_log(
                    window,
                    "Adjusted legacy custom ASR latency settings to balanced defaults (see user-data/config.json).",
                )
            # Local ASR stays in this pywebview window: bootstrap venv deps here, then start
            # backend via .venv\\Scripts\\python.exe (PortAudio runs in that subprocess).
            # Do not reexec desktop.launcher тАФ that opened a second desktop window on Windows.
            bootstrapper = RuntimeBootstrapper(
                paths=self._paths,
                log=lambda message: self._publish_window_log(window, message),
                status=lambda message: self._publish_window_status(window, message),
                register_process=lambda process: self._register_child_process(
                    process, role="bootstrap_install"
                ),
                unregister_process=lambda process: self._unregister_child_process(
                    process, role="bootstrap_install"
                ),
            )
            install_profile = install_profile_override
            if remote_role == "controller":
                self._publish_window_log(
                    window,
                    "Dependency path: controller (base only тАФ requirements.runtime.base.txt)",
                )
                python_exe = bootstrapper.ensure_base_environment()
            elif startup_mode == STARTUP_MODE_LOCAL:
                self._publish_window_log(
                    window,
                    "Dependency path: local ASR (base + torch + requirements.runtime.ai.txt / NeMo)",
                )
                install_profile = bootstrapper.ensure_local_asr_runtime(
                    install_profile_override=install_profile_override,
                )
                python_exe = self._paths.venv_python
            else:
                self._publish_window_log(
                    window,
                    "Dependency path: Browser Speech quick start (base only тАФ requirements.runtime.base.txt)",
                )
                python_exe = bootstrapper.ensure_base_environment()
            bootstrapper.cleanup_transient_runtime_files(preserve_paths=[self._log_path])
            self._apply_startup_mode_to_config(
                startup_mode,
                install_profile,
                remote_role=remote_role,
                allow_lan=allow_lan,
            )
            self._context = LaunchContext(
                **{
                    **asdict(self._context),
                    "worker_launch_browser": _load_worker_launch_browser_preference(self._paths.data_dir / "config.json"),
                    "startup_mode": startup_mode,
                    "web_speech_only": self._web_speech_only,
                    "install_profile": install_profile,
                    "remote_role": remote_role,
                    "profile_name": _load_profile_name(self._paths.data_dir / "config.json"),
                }
            )

            env = bootstrapper.runtime_environment()
            env["SST_REMOTE_ROLE"] = remote_role
            env["SST_ALLOW_LAN"] = "1" if allow_lan else "0"
            env["SST_DESKTOP_LAUNCHER"] = "1"
            env["SST_PYTHON_EXECUTABLE"] = str(python_exe)
            self._log_launch_context(python_exe=python_exe, env=env)
            self._start_backend_process(window, python_exe, env, remote_role=remote_role, allow_lan=allow_lan)
            self._publish_window_status(window, status_key="launcher.status.health_wait")
            dashboard_http_url = f"{self._context.base_url}/"

            def on_http_retry(attempt: int, last_error: str | None) -> None:
                if attempt == 1 or attempt % 10 == 0:
                    detail = last_error or "unknown"
                    self._publish_window_log(window, f"server wait attempt {attempt}: {detail}")

            _wait_for_http_ok(
                dashboard_http_url,
                timeout_seconds=240,
                abort_if=self._backend_abort_reason,
                on_retry=on_http_retry,
            )

            self._publish_window_log(window, "http server ready; loading dashboard window")
            self._publish_window_status(window, status_key="launcher.status.backend_ready")
            self._navigate_to_dashboard(window, self._context.dashboard_url)

            def verify_health_after_dashboard() -> None:
                try:
                    health = _wait_for_health(
                        f"{self._context.base_url}/api/health",
                        timeout_seconds=240,
                        abort_if=self._backend_abort_reason,
                    )
                    status = str(health.get("status", "ok"))
                    if status.lower() != "ok":
                        self._write_log(
                            f"health check after dashboard load returned unexpected status: {status}"
                        )
                        return
                    self._write_log("health ready after dashboard load")
                    self._apply_dashboard_resize(window, trigger="health ready")
                except Exception as exc:
                    self._write_log(
                        "health check after dashboard load failed: "
                        f"{type(exc).__name__}: {exc}"
                    )

            threading.Thread(target=verify_health_after_dashboard, daemon=True).start()
            self._start_runtime_metrics_monitor()
        except LaunchSelectionCancelled:
            self._startup_error_message = None
            self._write_log("bootstrap ended: launch selection cancelled (window closed before startup mode)")
            return
        except Exception as exc:
            details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            self._startup_error_message = details or str(exc)
            self._publish_window_log(window, f"bootstrap failed: {self._startup_error_message}")
            recent_backend_log = "\n".join(list(self._backend_tail)[-16:])
            if recent_backend_log:
                self._publish_window_log(window, "recent backend log tail follows")
                for line in recent_backend_log.splitlines():
                    self._publish_window_log(window, line)
            _show_error_dialog(
                f"{APP_NAME} Startup Error",
                f"{self._startup_error_message}\n\nLauncher log:\n{self._log_path}",
            )
            try:
                window.destroy()
            except Exception:
                pass

    def shutdown(self) -> None:
        if self._shutdown_started.is_set():
            return
        self._shutdown_started.set()
        self._write_log("shutdown started")
        with self._child_process_lock:
            tracked = [
                {"role": getattr(p, "_sst_subprocess_role", "child"), "pid": p.pid, "poll": p.poll()}
                for p in self._child_processes
            ]
        subprocess_trace("desktop", "shutdown_begin", tracked_children=tracked, child_count=len(tracked))
        if self._backend_server is not None:
            try:
                self._backend_server.stop()
            except Exception as exc:
                self._write_log(f"backend in-process stop: {type(exc).__name__}: {exc}")
            self._backend_server = None
        if self._backend_process is not None:
            self._terminate_process(self._backend_process, label="backend subprocess")
            self._backend_process = None
        with self._child_process_lock:
            remaining = list(self._child_processes)
        for process in remaining:
            role = str(getattr(process, "_sst_subprocess_role", "child") or "child")
            self._terminate_process(process, label=role)
        subprocess_trace("desktop", "shutdown_complete", child_count=0)
        self._write_log("shutdown completed")

    def run(self) -> int:
        os.environ.setdefault("PYWEBVIEW_GUI", "edgechromium")
        # Splash must stay interactive: profile selection happens in bootstrap()
        # via _wait_for_launch_option_selection(); startup continues in this window only.
        try:
            import webview
        except Exception as exc:
            _show_error_dialog(
                f"{APP_NAME} Startup Error",
                f"Desktop shell dependencies are missing: {exc}",
            )
            return 1

        initial_locale = self._current_ui_language()
        splash_sizes = SPLASH_WINDOW_WEB_ONLY if self._web_speech_only else SPLASH_WINDOW_DEFAULT
        window = webview.create_window(
            APP_NAME,
            html=_build_splash_html(
                APP_NAME,
                locale=initial_locale,
                web_speech_only=self._web_speech_only,
            ),
            js_api=DesktopApi(
                lambda: self._context,
                external_url_opener=self._open_external_url,
                launch_mode_selector=self._set_launch_option,
                window_getter=lambda: self._main_window,
            ),
            width=splash_sizes["width"],
            height=splash_sizes["height"],
            min_size=(splash_sizes["min_width"], splash_sizes["min_height"]),
            confirm_close=False,
            background_color="#09111b",
        )
        self._main_window = window
        window.events.closed += lambda: self.shutdown()
        loaded_hook = getattr(window.events, "loaded", None)
        if loaded_hook is not None:
            loaded_hook += lambda: self._on_desktop_window_loaded(window)

        pywebview_storage = str(self._paths.runtime_root / "pywebview-profile")
        pywebview_gui = os.environ.get("PYWEBVIEW_GUI", "edgechromium")
        ui_trace(
            "desktop",
            "pywebview",
            "webview_start",
            gui=pywebview_gui,
            storage_path=pywebview_storage,
            debug_webview=self._debug_webview,
            web_speech_only=self._web_speech_only,
        )
        try:
            webview.start(
                self.bootstrap,
                window,
                gui=pywebview_gui,
                debug=self._debug_webview,
                storage_path=pywebview_storage,
            )
        except Exception as exc:
            _show_error_dialog(
                f"{APP_NAME} Startup Error",
                f"Desktop window failed to initialize: {exc}",
            )
            self.shutdown()
            return 1

        self.shutdown()
        return 1 if self._startup_error_message else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Stream Subtitle Translator desktop launcher.")
    parser.add_argument("--debug-webview", action="store_true", help="Enable pywebview debug mode.")
    parser.add_argument(
        "--web-speech-only",
        action="store_true",
        help="Skip startup profile selection and always launch Browser Speech quick start.",
    )
    args = parser.parse_args()
    raise SystemExit(
        DesktopLauncher(
            debug_webview=args.debug_webview,
            web_speech_only=args.web_speech_only,
        ).run()
    )


if __name__ == "__main__":
    main()
