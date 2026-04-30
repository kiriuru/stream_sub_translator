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
from urllib.request import urlopen

from desktop.runtime_bootstrap import (
    RuntimeBootstrapper,
    auto_detect_install_profile,
    detect_runtime_paths,
    normalize_install_profile,
)


APP_HOST = "127.0.0.1"
APP_PORT = 8765
APP_NAME = "Stream Subtitle Translator"
STARTUP_MODE_BROWSER = "browser_google"
STARTUP_MODE_LOCAL = "local"
LAUNCH_OPTION_BROWSER = "browser_google"
LAUNCH_OPTION_NVIDIA = "nvidia"
LAUNCH_OPTION_CPU = "cpu"
LAUNCH_OPTION_REMOTE_CONTROLLER = "remote_controller"
LAUNCH_OPTION_REMOTE_WORKER = "remote_worker"


def _show_error_dialog(title: str, message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        print(f"{title}: {message}")


def _build_splash_html(title: str) -> str:
    payload = {
        "title": title,
        "subtitle": "Preparing the local runtime, backend, and dashboard window...",
        "detail": "All startup and dependency work now runs through the desktop launcher window.",
    }
    escaped = json.dumps(payload)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #09111b;
        --panel: rgba(14, 24, 40, 0.92);
        --line: rgba(160, 193, 255, 0.18);
        --text: #f5f7fb;
        --muted: #9cb0d0;
        --accent: #6cc7ff;
        --accent-strong: #7be3ad;
        --button: rgba(108, 199, 255, 0.12);
        --button-active: rgba(108, 199, 255, 0.24);
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: "Segoe UI", Tahoma, sans-serif;
        background:
          radial-gradient(circle at top, rgba(108, 199, 255, 0.14), transparent 40%),
          linear-gradient(180deg, #0b1422 0%, var(--bg) 100%);
        color: var(--text);
      }}
      .splash {{
        width: min(720px, calc(100vw - 48px));
        padding: 32px;
        border-radius: 24px;
        border: 1px solid var(--line);
        background: var(--panel);
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
      }}
      .eyebrow {{
        margin: 0 0 12px;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 12px;
        color: var(--accent);
      }}
      h1 {{
        margin: 0;
        font-size: 34px;
        line-height: 1.08;
      }}
      p {{
        margin: 14px 0 0;
        color: var(--muted);
        line-height: 1.6;
      }}
      .loader {{
        display: grid;
        grid-template-columns: 18px 1fr;
        gap: 14px;
        margin-top: 22px;
      }}
      .status {{
        margin: 0;
        color: #dce7ff;
        font-size: 14px;
      }}
      .log-panel {{
        margin-top: 20px;
        padding: 14px 16px;
        border-radius: 16px;
        border: 1px solid rgba(160, 193, 255, 0.12);
        background: rgba(6, 12, 20, 0.72);
      }}
      .profile-panel {{
        margin-top: 22px;
        padding: 16px;
        border-radius: 18px;
        border: 1px solid rgba(160, 193, 255, 0.14);
        background: rgba(7, 14, 24, 0.84);
      }}
      .profile-title {{
        margin: 0 0 8px;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--muted);
      }}
      .profile-hint {{
        margin: 0 0 14px;
        color: var(--muted);
        font-size: 14px;
      }}
      .profile-actions {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
      }}
      .profile-secondary {{
        margin-top: 14px;
        border-top: 1px solid rgba(160, 193, 255, 0.1);
        padding-top: 12px;
      }}
      .profile-secondary summary {{
        cursor: pointer;
        color: var(--muted);
        font-size: 13px;
        font-weight: 600;
      }}
      .profile-secondary[open] summary {{
        margin-bottom: 12px;
      }}
      .profile-secondary-actions {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }}
      .profile-button {{
        appearance: none;
        border: 1px solid rgba(160, 193, 255, 0.18);
        border-radius: 16px;
        background: var(--button);
        color: var(--text);
        padding: 16px 14px;
        text-align: left;
        cursor: pointer;
        transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
      }}
      .profile-button:hover {{
        transform: translateY(-1px);
        border-color: rgba(124, 227, 173, 0.36);
      }}
      .profile-button.active {{
        background: var(--button-active);
        border-color: rgba(124, 227, 173, 0.42);
      }}
      .profile-button[data-mode="browser_google"].active {{
        border-color: rgba(108, 199, 255, 0.46);
      }}
      .profile-button strong {{
        display: block;
        font-size: 16px;
        margin-bottom: 6px;
      }}
      .profile-button small {{
        display: block;
        color: var(--muted);
        line-height: 1.45;
      }}
      .profile-button-minimal {{
        padding: 13px 14px;
        border-radius: 14px;
      }}
      .profile-button-minimal strong {{
        font-size: 14px;
        margin-bottom: 4px;
      }}
      .log-title {{
        margin: 0 0 10px;
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.14em;
      }}
      #dev-log {{
        width: 100%;
        min-height: 280px;
        max-height: 280px;
        overflow: auto;
        white-space: pre-wrap;
        font-size: 13px;
        line-height: 1.5;
        color: #d7e5ff;
        border: 0;
        background: transparent;
        resize: none;
        padding: 0;
        user-select: text;
        -webkit-user-select: text;
      }}
      .splash-footer {{
        margin-top: 18px;
        text-align: center;
        font-size: 12px;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: rgba(156, 176, 208, 0.92);
      }}
      .spinner {{
        width: 18px;
        height: 18px;
        border: 2px solid rgba(255, 255, 255, 0.16);
        border-top-color: var(--accent);
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }}
      @media (max-width: 760px) {{
        .profile-actions {{
          grid-template-columns: 1fr;
        }}
      }}
      @keyframes spin {{
        to {{
          transform: rotate(360deg);
        }}
      }}
    </style>
  </head>
  <body>
    <main class="splash"></main>
    <script>
      const payload = {escaped};
      document.querySelector(".splash").innerHTML = `
        <p class="eyebrow">Desktop Launcher</p>
        <h1>${{payload.title}}</h1>
        <p>${{payload.subtitle}}</p>
        <div class="loader">
          <div class="spinner" aria-hidden="true"></div>
          <div>
            <p id="status-line" class="status">${{payload.detail}}</p>
          </div>
        </div>
        <section class="profile-panel">
          <p class="profile-title">Runtime Profile</p>
          <p id="profile-hint" class="profile-hint">Choose how this desktop session should start.</p>
          <div class="profile-actions">
            <button id="profile-browser" class="profile-button" data-mode="browser_google" type="button" onclick="window.__sstChooseLaunchOption('browser_google')">
              <strong>Quick Start</strong>
              <small>Browser Speech only. Opens the dashboard fast and skips local AI runtime installation.</small>
            </button>
            <button id="profile-nvidia" class="profile-button" data-mode="nvidia" type="button" onclick="window.__sstChooseLaunchOption('nvidia')">
              <strong>NVIDIA GPU (CUDA)</strong>
              <small>Recommended for NVIDIA cards. Uses the GPU-first PyTorch runtime.</small>
            </button>
            <button id="profile-cpu" class="profile-button" data-mode="cpu" type="button" onclick="window.__sstChooseLaunchOption('cpu')">
              <strong>CPU-only</strong>
              <small>Recommended for AMD, Intel, or no-GPU machines.</small>
            </button>
          </div>
          <details class="profile-secondary">
            <summary>Remote modes</summary>
            <div class="profile-secondary-actions">
              <button id="profile-remote-controller" class="profile-button profile-button-minimal" data-mode="remote_controller" type="button" onclick="window.__sstChooseLaunchOption('remote_controller')">
                <strong>Remote Controller</strong>
                <small>Lightweight controller session for pairing with a worker on your LAN.</small>
              </button>
              <button id="profile-remote-worker" class="profile-button profile-button-minimal" data-mode="remote_worker" type="button" onclick="window.__sstChooseLaunchOption('remote_worker')">
                <strong>Remote Worker</strong>
                <small>Local AI worker session with LAN bind enabled for a controller.</small>
              </button>
            </div>
          </details>
        </section>
        <section class="log-panel">
          <p class="log-title">Startup Dev Log</p>
          <textarea id="dev-log" readonly spellcheck="false">launcher: splash ready</textarea>
        </section>
        <div class="splash-footer">Powered by Kiriuru</div>
      `;
      window.__sstSetLaunchOptionPrompt = function (payload) {{
        const normalized = payload || {{}};
        const hintEl = document.getElementById("profile-hint");
        const browserButton = document.getElementById("profile-browser");
        const nvidiaButton = document.getElementById("profile-nvidia");
        const cpuButton = document.getElementById("profile-cpu");
        const remoteControllerButton = document.getElementById("profile-remote-controller");
        const remoteWorkerButton = document.getElementById("profile-remote-worker");
        const selected = String(normalized.selected || "").toLowerCase();
        if (hintEl) {{
          hintEl.textContent = normalized.hint || "Choose how this desktop session should start.";
        }}
        if (browserButton) {{
          browserButton.classList.toggle("active", selected === "browser_google");
          browserButton.disabled = Boolean(normalized.locked);
        }}
        if (nvidiaButton) {{
          nvidiaButton.classList.toggle("active", selected === "nvidia");
          nvidiaButton.disabled = Boolean(normalized.locked);
        }}
        if (cpuButton) {{
          cpuButton.classList.toggle("active", selected === "cpu");
          cpuButton.disabled = Boolean(normalized.locked);
        }}
        if (remoteControllerButton) {{
          remoteControllerButton.classList.toggle("active", selected === "remote_controller");
          remoteControllerButton.disabled = Boolean(normalized.locked);
        }}
        if (remoteWorkerButton) {{
          remoteWorkerButton.classList.toggle("active", selected === "remote_worker");
          remoteWorkerButton.disabled = Boolean(normalized.locked);
        }}
      }};
      window.__sstChooseLaunchOption = function (selection) {{
        if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.choose_launch_mode !== "function") {{
          return;
        }}
        const normalized = String(selection || "").toLowerCase();
        const applyingHint = normalized === "browser_google"
          ? "Applying the Browser Speech quick start mode..."
          : normalized === "remote_controller"
          ? "Applying the remote controller startup mode..."
          : normalized === "remote_worker"
          ? "Applying the remote worker startup mode..."
          : "Applying the selected local AI runtime profile...";
        window.__sstSetLaunchOptionPrompt({{ selected: normalized, locked: true, hint: applyingHint }});
        window.pywebview.api.choose_launch_mode(normalized);
      }};
      window.__sstDesktopLog = function (message) {{
        const el = document.getElementById("dev-log");
        if (!el) return;
        el.value += `\\n${{message}}`;
        el.scrollTop = el.scrollHeight;
      }};
      window.__sstDesktopStatus = function (message) {{
        const el = document.getElementById("status-line");
        if (!el) return;
        el.textContent = message;
      }};
    </script>
  </body>
</html>"""


@dataclass(frozen=True)
class LaunchContext:
    desktop_mode: bool
    base_url: str
    dashboard_url: str
    overlay_url: str
    browser_worker_url: str
    startup_mode: str
    install_profile: str
    remote_role: str
    profile_name: str
    project_root: str
    data_dir: str


def _load_profile_name(config_path: Path) -> str:
    if not config_path.exists():
        return "default"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return "default"
    profile = str(payload.get("profile", "default") or "default").strip()
    return profile or "default"


def _load_saved_asr_mode(config_path: Path) -> str:
    if not config_path.exists():
        return STARTUP_MODE_LOCAL
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return STARTUP_MODE_LOCAL
    asr = payload.get("asr", {}) if isinstance(payload, dict) else {}
    if not isinstance(asr, dict):
        return STARTUP_MODE_LOCAL
    mode = str(asr.get("mode", STARTUP_MODE_LOCAL) or STARTUP_MODE_LOCAL).strip().lower()
    return mode if mode in {STARTUP_MODE_LOCAL, STARTUP_MODE_BROWSER} else STARTUP_MODE_LOCAL


def _read_install_profile(install_profile_file: Path) -> str:
    if not install_profile_file.exists():
        return "auto"
    try:
        value = install_profile_file.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "auto"
    return value if value in {"cpu", "nvidia"} else "auto"


class DesktopApi:
    def __init__(
        self,
        context_getter: callable,
        *,
        external_url_opener: callable,
        launch_mode_selector: callable,
    ) -> None:
        self._context_getter = context_getter
        self._external_url_opener = external_url_opener
        self._launch_mode_selector = launch_mode_selector

    def get_launch_context(self) -> dict[str, Any]:
        return asdict(self._context_getter())

    def open_external_url(self, url: str) -> bool:
        return bool(self._external_url_opener(str(url or "").strip()))

    def choose_launch_mode(self, selection: str) -> bool:
        return bool(self._launch_mode_selector(str(selection or "").strip()))


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _describe_port_owner(port: int) -> str | None:
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    marker = f":{port}"
    for line in completed.stdout.splitlines():
        if marker not in line or "LISTENING" not in line.upper():
            continue
        parts = [part for part in line.split() if part]
        if len(parts) < 5:
            continue
        pid = parts[-1]
        return f"Detected another process listening on port {port} (PID {pid})."
    return None


def _wait_for_health(
    health_url: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: float = 1.0,
    abort_if: callable | None = None,
    on_retry: callable | None = None,
) -> dict[str, Any]:
    started_at = time.monotonic()
    attempt = 0
    last_error: str | None = None
    while time.monotonic() - started_at < timeout_seconds:
        if abort_if is not None:
            abort_message = abort_if()
            if abort_message:
                raise RuntimeError(abort_message)
        attempt += 1
        try:
            with urlopen(health_url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if isinstance(payload, dict):
                    return payload
                raise RuntimeError("Local health endpoint returned a non-object JSON payload.")
        except Exception as exc:
            last_error = str(exc)
            if on_retry is not None:
                on_retry(attempt, last_error)
            time.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"Health check did not become ready within {timeout_seconds}s. "
        f"Last error: {last_error or 'unknown'}"
    )


class DesktopLauncher:
    def __init__(self, *, debug_webview: bool = False) -> None:
        self._paths = detect_runtime_paths()
        self._debug_webview = debug_webview
        self._log_path = self._paths.logs_dir / "desktop-launcher.log"
        self._legacy_log_path = self._paths.project_root / ".tmp" / "desktop-launcher.log"
        self._ensure_launcher_log_files()
        self._shutdown_started = threading.Event()
        self._startup_error_message: str | None = None
        self._child_processes: set[subprocess.Popen[str]] = set()
        self._child_process_lock = threading.Lock()
        self._backend_process: subprocess.Popen[str] | None = None
        self._backend_tail: deque[str] = deque(maxlen=80)
        self._backend_output_thread: threading.Thread | None = None
        self._launch_option_event = threading.Event()
        self._selected_launch_option: str | None = None
        self._selected_launch_option_lock = threading.Lock()
        self._browser_worker_last_error: str | None = None
        self._context = self._build_context()
        self._write_log("launcher initialized")

    def _ensure_launcher_log_files(self) -> None:
        log_dir = self._paths.logs_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        if self._legacy_log_path.exists():
            try:
                self._legacy_log_path.unlink()
            except OSError:
                pass
        for log_path in (
            self._log_path,
            log_dir / "dashboard-live-events.log",
            log_dir / "overlay-events.log",
            log_dir / "browser-recognition.log",
        ):
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("", encoding="utf-8")

    def _build_context(self) -> LaunchContext:
        base_url = f"http://{APP_HOST}:{APP_PORT}"
        return LaunchContext(
            desktop_mode=True,
            base_url=base_url,
            dashboard_url=f"{base_url}/?desktop=1",
            overlay_url=f"{base_url}/overlay",
            browser_worker_url=f"{base_url}/google-asr",
            startup_mode=_load_saved_asr_mode(self._paths.data_dir / "config.json"),
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

    def _publish_window_log(self, window: Any, message: str) -> None:
        self._write_log(message)
        try:
            window.evaluate_js(f"window.__sstDesktopLog && window.__sstDesktopLog({json.dumps(message)});")
        except Exception:
            pass

    def _publish_window_status(self, window: Any, message: str) -> None:
        self._write_log(f"status: {message}")
        try:
            window.evaluate_js(f"window.__sstDesktopStatus && window.__sstDesktopStatus({json.dumps(message)});")
        except Exception:
            pass

    def _register_child_process(self, process: subprocess.Popen[str]) -> None:
        with self._child_process_lock:
            self._child_processes.add(process)

    def _unregister_child_process(self, process: subprocess.Popen[str]) -> None:
        with self._child_process_lock:
            self._child_processes.discard(process)

    def _terminate_process(self, process: subprocess.Popen[str], *, label: str) -> None:
        if process.poll() is not None:
            self._unregister_child_process(process)
            return
        self._write_log(f"{label}: terminate requested")
        try:
            process.terminate()
            process.wait(timeout=15)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass
        finally:
            self._unregister_child_process(process)

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
        saved_label = "saved" if saved_profile else "detected"
        selected_label = (
            "Quick Start (Browser Speech)"
            if selected == LAUNCH_OPTION_BROWSER
            else "NVIDIA GPU (CUDA 12.8)"
            if selected == LAUNCH_OPTION_NVIDIA
            else "Remote Controller"
            if selected == LAUNCH_OPTION_REMOTE_CONTROLLER
            else "Remote Worker"
            if selected == LAUNCH_OPTION_REMOTE_WORKER
            else "CPU-only"
        )
        detected_label = "NVIDIA GPU" if detected_profile == "nvidia" else "CPU-only"
        saved_mode_label = "Browser Speech quick start" if saved_asr_mode == STARTUP_MODE_BROWSER else "Local AI"
        hint = (
            f"Choose how this desktop session should start. "
            f"Saved recognition mode: {saved_mode_label}. "
            f"Current {saved_label} local AI profile: {saved_profile or detected_profile}. "
            f"Auto-detected local AI recommendation: {detected_label}. "
            f"Remote modes stay secondary and use LAN pairing when selected. "
            f"Selected: {selected_label}."
        )
        payload = {"selected": selected, "hint": hint, "locked": False}
        try:
            window.evaluate_js(
                f"window.__sstSetLaunchOptionPrompt && window.__sstSetLaunchOptionPrompt({json.dumps(payload)});"
            )
        except Exception:
            pass

    def _wait_for_launch_option_selection(self, window: Any) -> tuple[str, str | None, str, bool]:
        saved_profile = normalize_install_profile(_read_install_profile(self._paths.install_profile_file))
        detected_profile = auto_detect_install_profile()
        saved_asr_mode = _load_saved_asr_mode(self._paths.data_dir / "config.json")
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
        self._publish_window_status(
            window,
            "Choose Browser Speech, CPU, or GPU to continue. Remote modes are available under the secondary Remote block.",
        )
        self._publish_window_log(
            window,
            f"launch selector ready: saved_mode={saved_asr_mode}, saved_install={saved_profile or 'none'}, detected={detected_profile}, selected={selected}",
        )
        while not self._launch_option_event.wait(timeout=0.2):
            if self._shutdown_started.is_set():
                raise RuntimeError("Desktop launcher was closed before the startup mode was selected.")
        chosen = self._selected_launch_mode() or selected
        if chosen == LAUNCH_OPTION_BROWSER:
            fallback_install_profile = saved_profile or detected_profile
            self._publish_window_status(window, "Preparing lightweight Browser Speech startup...")
            return STARTUP_MODE_BROWSER, fallback_install_profile, "disabled", False
        if chosen == LAUNCH_OPTION_REMOTE_CONTROLLER:
            self._publish_window_status(window, "Preparing lightweight remote controller startup...")
            return STARTUP_MODE_LOCAL, None, "controller", False
        if chosen == LAUNCH_OPTION_REMOTE_WORKER:
            effective_profile = saved_profile or detected_profile
            worker_profile_label = "NVIDIA GPU" if effective_profile == "nvidia" else "CPU-only"
            self._publish_window_status(window, f"Preparing remote worker startup with {worker_profile_label} local AI...")
            return STARTUP_MODE_LOCAL, effective_profile, "worker", True
        self._publish_window_status(
            window,
            "Preparing the local environment for NVIDIA GPU..." if chosen == LAUNCH_OPTION_NVIDIA else "Preparing the local CPU-only environment...",
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
        payload: dict[str, Any]
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text(encoding="utf-8"))
                payload = existing if isinstance(existing, dict) else {}
            except Exception:
                payload = {}
        else:
            payload = {}
        asr = payload.get("asr", {})
        if not isinstance(asr, dict):
            asr = {}
        asr["mode"] = STARTUP_MODE_BROWSER if startup_mode == STARTUP_MODE_BROWSER else STARTUP_MODE_LOCAL
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

    def _normalize_external_url(self, url: str) -> str:
        return urljoin(f"{self._context.base_url}/", str(url or "").strip())

    def _set_browser_worker_error(self, message: str) -> None:
        detail = str(message or "").strip() or "Unknown browser worker launch failure."
        self._browser_worker_last_error = detail
        self._write_log(f"[browser-worker] {detail}")

    def _is_windowsapps_alias(self, candidate: Path) -> bool:
        try:
            return "windowsapps" in str(candidate.resolve()).lower()
        except Exception:
            return "windowsapps" in str(candidate).lower()

    def _is_supported_chromium_path(self, candidate: Path | None) -> bool:
        if candidate is None:
            return False
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        if not resolved.exists() or not resolved.is_file():
            return False
        if self._is_windowsapps_alias(resolved):
            return False
        return resolved.name.lower() in {"chrome.exe", "msedge.exe", "chromium.exe"}

    def _resolve_browser_from_app_paths(self, executable_name: str) -> Path | None:
        subkey = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}"
        hives = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
        wow64_flags = (0, getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0))
        for hive in hives:
            for flag in wow64_flags:
                try:
                    access = winreg.KEY_READ | flag
                    with winreg.OpenKey(hive, subkey, 0, access) as key:
                        value, _ = winreg.QueryValueEx(key, None)
                except OSError as exc:
                    self._write_log(
                        f"[browser-worker] registry miss for {executable_name} in hive={hive} flag={flag}: {exc}"
                    )
                    continue
                candidate = Path(str(value or "").strip().strip('"'))
                self._write_log(
                    f"[browser-worker] registry candidate for {executable_name}: {candidate}"
                )
                if self._is_supported_chromium_path(candidate):
                    return candidate
                self._write_log(
                    f"[browser-worker] rejected registry candidate for {executable_name}: {candidate}"
                )
        return None

    def _find_chromium_browser(self) -> Path | None:
        candidate_names = ("chrome.exe", "chromium.exe", "msedge.exe")
        seen: set[str] = set()
        for candidate_name in candidate_names:
            registry_path = self._resolve_browser_from_app_paths(candidate_name)
            if registry_path is not None:
                registry_key = str(registry_path).lower()
                if registry_key not in seen:
                    seen.add(registry_key)
                    self._write_log(f"[browser-worker] selected browser from registry: {registry_path}")
                    return registry_path
        for candidate in candidate_names:
            resolved = shutil.which(candidate)
            if not resolved:
                self._write_log(f"[browser-worker] PATH lookup miss: {candidate}")
                continue
            resolved_path = Path(resolved)
            self._write_log(f"[browser-worker] PATH candidate for {candidate}: {resolved_path}")
            if not self._is_supported_chromium_path(resolved_path):
                self._write_log(f"[browser-worker] Ignoring unsupported browser alias: {resolved_path}")
                continue
            resolved_key = str(resolved_path).lower()
            if resolved_key not in seen:
                seen.add(resolved_key)
                self._write_log(f"[browser-worker] selected browser from PATH: {resolved_path}")
                return resolved_path
        roots = [
            os.environ.get("LOCALAPPDATA", ""),
            os.environ.get("ProgramFiles", ""),
            os.environ.get("ProgramFiles(x86)", ""),
        ]
        relative_candidates = (
            ("Google", "Chrome", "Application", "chrome.exe"),
            ("Chromium", "Application", "chrome.exe"),
            ("Microsoft", "Edge", "Application", "msedge.exe"),
        )
        for root in roots:
            if not root:
                continue
            for parts in relative_candidates:
                candidate = Path(root).joinpath(*parts)
                self._write_log(f"[browser-worker] filesystem candidate: {candidate}")
                if self._is_supported_chromium_path(candidate):
                    self._write_log(f"[browser-worker] selected browser from filesystem probe: {candidate}")
                    return candidate
                self._write_log(f"[browser-worker] rejected filesystem candidate: {candidate}")
        return None

    def _is_browser_worker_url(self, normalized_url: str) -> bool:
        try:
            return urlparse(normalized_url).path.rstrip("/").lower() == "/google-asr"
        except Exception:
            return False

    def _open_browser_worker_window(self, normalized_url: str) -> bool:
        self._browser_worker_last_error = None
        browser_path = self._find_chromium_browser()
        if browser_path is None:
            self._set_browser_worker_error(
                "Could not find a usable Chrome/Chromium/Edge executable for Browser Speech worker launch."
            )
            _show_error_dialog(
                f"{APP_NAME} Browser Speech Error",
                "Could not find Chrome, Chromium, or Microsoft Edge for Browser Speech.\n\n"
                f"See launcher log:\n{self._log_path}",
            )
            return False
        args = [
            str(browser_path),
            f"--app={normalized_url}",
            "--new-window",
            "--disable-session-crashed-bubble",
            "--window-size=980,860",
        ]
        self._write_log(f"[browser-worker] launch args: {args}")
        try:
            subprocess.Popen(
                args,
                cwd=str(browser_path.parent),
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            self._write_log(f"[browser-worker] launched app window via {browser_path}")
            return True
        except Exception as exc:
            self._set_browser_worker_error(
                f"Failed to launch Browser Speech worker via {browser_path}: {type(exc).__name__}: {exc}"
            )
            _show_error_dialog(
                f"{APP_NAME} Browser Speech Error",
                "Browser Speech could not open a dedicated Chrome/Chromium window.\n\n"
                f"Reason: {type(exc).__name__}: {exc}\n\n"
                f"See launcher log:\n{self._log_path}",
            )
            return False

    def _is_noise_backend_line(self, line: str) -> bool:
        normalized = str(line or "")
        return (
            '"GET /api/runtime/status HTTP/1.1" 200 OK' in normalized
            or '"GET /api/health HTTP/1.1" 200 OK' in normalized
            or '"POST /api/logs/client-event HTTP/1.1" 200 OK' in normalized
        )

    def _open_external_url(self, url: str) -> bool:
        normalized = self._normalize_external_url(url)
        if not normalized:
            return False
        if self._is_browser_worker_url(normalized):
            return self._open_browser_worker_window(normalized)
        try:
            if os.name == "nt":
                os.startfile(normalized)  # type: ignore[attr-defined]
                return True
        except Exception:
            pass
        return bool(webbrowser.open(normalized))

    def _format_port_error(self) -> str:
        owner = _describe_port_owner(APP_PORT)
        lines = [
            f"Cannot start {APP_NAME} because {APP_HOST}:{APP_PORT} is already in use.",
        ]
        if owner:
            lines.append(owner)
        lines.append("Close the previous local app instance or free the port, then launch the desktop app again.")
        return "\n".join(lines)

    def _start_backend_process(
        self,
        window: Any,
        python_exe: Path,
        env: dict[str, str],
        *,
        remote_role: str = "disabled",
        allow_lan: bool = False,
    ) -> None:
        self._publish_window_status(window, "Starting local backend subprocess on 127.0.0.1 ...")
        bootstrap_code = (
            "import runpy, sys; "
            f"sys.path.insert(0, {self._paths.bundle_root.as_posix()!r}); "
            "runpy.run_module('backend.run', run_name='__main__')"
        )
        args = [str(python_exe), "-u", "-c", bootstrap_code, "--remote-role", remote_role]
        if allow_lan:
            args.append("--allow-lan")
        process = subprocess.Popen(
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
        )
        self._backend_process = process
        self._register_child_process(process)
        self._publish_window_log(window, f"backend subprocess started via {python_exe}")

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
                self._unregister_child_process(process)

        self._backend_output_thread = threading.Thread(target=reader, daemon=True)
        self._backend_output_thread.start()

    def _backend_abort_reason(self) -> str | None:
        if self._backend_process is None:
            return None
        exit_code = self._backend_process.poll()
        if exit_code is None:
            return None
        tail = "\n".join(list(self._backend_tail)[-12:])
        detail = f"\n\nRecent backend log:\n{tail}" if tail else ""
        return f"Local backend exited during startup with code {exit_code}.{detail}"

    def bootstrap(self, window: Any) -> None:
        try:
            self._publish_window_log(window, "preflight started")
            if _is_port_in_use(APP_HOST, APP_PORT):
                raise RuntimeError(self._format_port_error())
            self._publish_window_log(window, "preflight passed")

            startup_mode, install_profile_override, remote_role, allow_lan = self._wait_for_launch_option_selection(window)
            bootstrapper = RuntimeBootstrapper(
                paths=self._paths,
                log=lambda message: self._publish_window_log(window, message),
                status=lambda message: self._publish_window_status(window, message),
                register_process=self._register_child_process,
                unregister_process=self._unregister_child_process,
            )
            install_profile = install_profile_override
            if remote_role == "controller":
                python_exe = bootstrapper.ensure_base_environment()
            elif startup_mode == STARTUP_MODE_LOCAL:
                install_profile = bootstrapper.ensure_local_asr_runtime(
                    install_profile_override=install_profile_override,
                )
                python_exe = self._paths.venv_python
            else:
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
                    "startup_mode": startup_mode,
                    "install_profile": install_profile,
                    "remote_role": remote_role,
                    "profile_name": _load_profile_name(self._paths.data_dir / "config.json"),
                }
            )

            env = bootstrapper.runtime_environment()
            env["SST_REMOTE_ROLE"] = remote_role
            env["SST_ALLOW_LAN"] = "1" if allow_lan else "0"
            self._start_backend_process(window, python_exe, env, remote_role=remote_role, allow_lan=allow_lan)
            self._publish_window_status(window, "Waiting for local /api/health ...")

            def on_health_retry(attempt: int, last_error: str | None) -> None:
                if attempt == 1 or attempt % 10 == 0:
                    detail = last_error or "unknown"
                    self._publish_window_log(window, f"health wait attempt {attempt}: {detail}")

            health = _wait_for_health(
                f"{self._context.base_url}/api/health",
                timeout_seconds=240,
                abort_if=self._backend_abort_reason,
                on_retry=on_health_retry,
            )
            status = str(health.get("status", "ok"))
            if status.lower() != "ok":
                raise RuntimeError(f"Local health check returned unexpected status: {status}")

            self._publish_window_log(window, "health ready; loading dashboard window")
            self._publish_window_status(window, "Backend ready. Loading dashboard...")
            window.load_url(self._context.dashboard_url)
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
        if self._backend_process is not None:
            self._terminate_process(self._backend_process, label="backend subprocess")
            self._backend_process = None
        with self._child_process_lock:
            remaining = list(self._child_processes)
        for process in remaining:
            self._terminate_process(process, label="child process")
        self._write_log("shutdown completed")

    def run(self) -> int:
        os.environ.setdefault("PYWEBVIEW_GUI", "edgechromium")
        try:
            import webview
        except Exception as exc:
            _show_error_dialog(
                f"{APP_NAME} Startup Error",
                f"Desktop shell dependencies are missing: {exc}",
            )
            return 1

        window = webview.create_window(
            APP_NAME,
            html=_build_splash_html(APP_NAME),
            js_api=DesktopApi(
                lambda: self._context,
                external_url_opener=self._open_external_url,
                launch_mode_selector=self._set_launch_option,
            ),
            width=1440,
            height=940,
            min_size=(1180, 760),
            confirm_close=False,
            background_color="#09111b",
        )
        window.events.closed += lambda: self.shutdown()

        try:
            webview.start(
                self.bootstrap,
                window,
                gui="edgechromium",
                debug=self._debug_webview,
                storage_path=str(self._paths.project_root / ".cache" / "pywebview"),
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
    args = parser.parse_args()
    raise SystemExit(DesktopLauncher(debug_webview=args.debug_webview).run())


if __name__ == "__main__":
    main()
