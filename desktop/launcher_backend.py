"""Backend subprocess/in-process startup and runtime metrics monitor."""
from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

from desktop.backend_host import (
    build_backend_subprocess_bootstrap,
    start_inprocess_backend,
    use_inprocess_backend,
)
from desktop.launcher_context import (
    APP_HOST,
    APP_NAME,
    APP_PORT,
    RUNTIME_METRICS_FROZEN_WARN_SECONDS,
    RUNTIME_METRICS_LOG_PREFIX,
    RUNTIME_METRICS_POLL_ACTIVE_SECONDS,
    RUNTIME_METRICS_POLL_IDLE_SECONDS,
    _RUNTIME_METRICS_ACTIVE_STATUSES,
    _describe_port_owner,
    _fetch_json_object,
    _format_runtime_metrics_log_line,
    _is_port_in_use,
    _runtime_metrics_progress_signature,
    _runtime_status_value,
)
from desktop.subprocess_trace import (
    log_subprocess_terminate,
    logged_popen,
    subprocess_trace,
)


class LauncherBackendMixin:
    def _register_child_process(self, process: subprocess.Popen[str], *, role: str = "child") -> None:
        with self._child_process_lock:
            self._child_processes.add(process)
        subprocess_trace("desktop", "child_registered", role=role, pid=process.pid)
    def _unregister_child_process(self, process: subprocess.Popen[str], *, role: str = "child") -> None:
        with self._child_process_lock:
            self._child_processes.discard(process)
        subprocess_trace("desktop", "child_unregistered", role=role, pid=process.pid)
    def _terminate_process(self, process: subprocess.Popen[str], *, label: str) -> None:
        existing_code = process.poll()
        if existing_code is not None:
            log_subprocess_terminate(
                process,
                role=label,
                action="already_exited",
                return_code=existing_code,
            )
            self._unregister_child_process(process, role=label)
            return
        self._write_log(f"{label}: terminate requested")
        log_subprocess_terminate(process, role=label, action="terminate_requested")
        return_code: int | None = None
        try:
            process.terminate()
            return_code = process.wait(timeout=15)
        except Exception:
            try:
                log_subprocess_terminate(process, role=label, action="kill_requested")
                process.kill()
                return_code = process.wait(timeout=5)
            except Exception:
                return_code = process.poll()
        finally:
            log_subprocess_terminate(
                process,
                role=label,
                action="exited",
                return_code=return_code if return_code is not None else process.poll(),
            )
            self._unregister_child_process(process, role=label)
    def _is_noise_backend_line(self, line: str) -> bool:
        normalized = str(line or "")
        return (
            '"GET /api/runtime/status HTTP/1.1" 200 OK' in normalized
            or '"GET /api/health HTTP/1.1" 200 OK' in normalized
            or '"POST /api/logs/client-event HTTP/1.1" 200 OK' in normalized
        )
    def _format_port_error(self) -> str:
        owner = _describe_port_owner(APP_PORT)
        lines = [
            f"Cannot start {APP_NAME} because {APP_HOST}:{APP_PORT} is already in use.",
        ]
        if owner:
            lines.append(owner)
        lines.append("Close the previous local app instance or free the port, then launch the desktop app again.")
        return "\n".join(lines)
    def _launcher_cli_argv(self) -> list[str]:
        argv: list[str] = []
        if self._debug_webview:
            argv.append("--debug-webview")
        if self._web_speech_only:
            argv.append("--web-speech-only")
        return argv
    def _ensure_backend_port_available(self) -> None:
        if _is_port_in_use(APP_HOST, APP_PORT):
            raise RuntimeError(self._format_port_error())
    def _start_backend_process(
        self,
        window: Any,
        python_exe: Path,
        env: dict[str, str],
        *,
        remote_role: str = "disabled",
        allow_lan: bool = False,
    ) -> None:
        self._ensure_backend_port_available()
        self._publish_window_status(window, status_key="launcher.status.backend_starting")
        if use_inprocess_backend():
            subprocess_trace(
                "desktop",
                "backend_start_inprocess",
                remote_role=remote_role,
                allow_lan=allow_lan,
            )
            self._start_backend_inprocess(window, env, remote_role=remote_role, allow_lan=allow_lan)
            return

        bootstrap_code = build_backend_subprocess_bootstrap(self._paths.bundle_root)
        args = [str(python_exe), "-u", "-c", bootstrap_code, "--remote-role", remote_role]
        if allow_lan:
            args.append("--allow-lan")
        process = logged_popen(
            "backend",
            args,
            cwd=str(self._paths.project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            watch_exit=True,
            description="local FastAPI backend (backend.run)",
            extra={
                "python_exe": str(python_exe),
                "remote_role": remote_role,
                "allow_lan": allow_lan,
                "inprocess_fallback": False,
            },
        )
        self._backend_process = process
        self._register_child_process(process, role="backend")
        self._publish_window_log(
            window,
            f"backend subprocess started via {python_exe} (same layout as start.bat; owns PortAudio on main thread)",
        )

        def reader() -> None:
            assert process.stdout is not None
            try:
                for raw_line in process.stdout:
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    if self._is_noise_backend_line(line):
                        continue
                    prefixed = f"[backend] {line}"
                    self._backend_tail.append(prefixed)
                    self._publish_window_log(window, prefixed)
            finally:
                role = str(getattr(process, "_sst_subprocess_role", "backend") or "backend")
                self._unregister_child_process(process, role=role)

        self._backend_output_thread = threading.Thread(target=reader, daemon=True)
        self._backend_output_thread.start()
    def _start_backend_inprocess(
        self,
        window: Any,
        env: dict[str, str],
        *,
        remote_role: str = "disabled",
        allow_lan: bool = False,
    ) -> None:
        self._backend_server = start_inprocess_backend(
            bundle_root=self._paths.bundle_root,
            env=env,
            host=APP_HOST,
            port=APP_PORT,
            remote_role=remote_role,
            allow_lan=allow_lan,
        )
        self._publish_window_log(
            window,
            "backend started in-process (SST_DESKTOP_BACKEND_INPROC=1; not recommended on Windows)",
        )
    def _backend_abort_reason(self) -> str | None:
        if self._backend_server is not None:
            if self._backend_server.startup_error is not None:
                return f"Local backend thread failed: {self._backend_server.startup_error}"
            if not self._backend_server.is_alive:
                return "Local backend thread exited during startup."
            return None
        if self._backend_process is None:
            return None
        exit_code = self._backend_process.poll()
        if exit_code is None:
            return None
        tail = "\n".join(list(self._backend_tail)[-12:])
        detail = f"\n\nRecent backend log:\n{tail}" if tail else ""
        return f"Local backend exited during startup with code {exit_code}.{detail}"
    def _start_runtime_metrics_monitor(self) -> None:
        if self._runtime_metrics_monitor_thread is not None:
            return
        self._write_log("runtime metrics monitor started")
        self._runtime_metrics_monitor_thread = threading.Thread(
            target=self._runtime_metrics_monitor_loop,
            daemon=True,
            name="sst-runtime-metrics",
        )
        self._runtime_metrics_monitor_thread.start()
    def _runtime_metrics_monitor_loop(self) -> None:
        status_url = f"{self._context.base_url}/api/runtime/status"
        last_status: str | None = None
        last_progress_signature: tuple[int, ...] | None = None
        last_progress_at: float | None = None
        last_frozen_warning_at: float | None = None

        while not self._shutdown_started.is_set():
            payload = _fetch_json_object(status_url)
            if payload is None:
                if self._shutdown_started.wait(timeout=10.0):
                    break
                continue

            status = _runtime_status_value(payload)
            is_running = bool(payload.get("is_running") or payload.get("running"))
            active = is_running or status in _RUNTIME_METRICS_ACTIVE_STATUSES
            line = _format_runtime_metrics_log_line(payload)

            if status != last_status:
                previous = last_status or "none"
                self._write_log(f"{line} (status change: {previous} -> {status})")
                last_status = status
                last_progress_signature = _runtime_metrics_progress_signature(payload)
                last_progress_at = time.monotonic()
                last_frozen_warning_at = None
            elif active:
                self._write_log(line)
                progress_signature = _runtime_metrics_progress_signature(payload)
                now = time.monotonic()
                if progress_signature != last_progress_signature:
                    last_progress_signature = progress_signature
                    last_progress_at = now
                    last_frozen_warning_at = None
                elif (
                    status == "listening"
                    and last_progress_at is not None
                    and (now - last_progress_at) >= RUNTIME_METRICS_FROZEN_WARN_SECONDS
                    and (
                        last_frozen_warning_at is None
                        or (now - last_frozen_warning_at) >= RUNTIME_METRICS_FROZEN_WARN_SECONDS
                    )
                ):
                    frozen_for = int(now - last_progress_at)
                    self._write_log(
                        f"{RUNTIME_METRICS_LOG_PREFIX} warning: VAD/ASR metrics unchanged for "
                        f"{frozen_for}s while listening (audio capture or VAD may be idle) | {line}"
                    )
                    last_frozen_warning_at = now

            interval = (
                RUNTIME_METRICS_POLL_ACTIVE_SECONDS if active else RUNTIME_METRICS_POLL_IDLE_SECONDS
            )
            if self._shutdown_started.wait(timeout=interval):
                break

        self._write_log("runtime metrics monitor stopped")
