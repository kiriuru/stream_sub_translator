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

from backend.core.remote_mode import (
    REMOTE_ROLE_CONTROLLER,
    REMOTE_ROLE_DISABLED,
    REMOTE_ROLE_WORKER,
    normalize_remote_role,
)
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
        "subtitle": "Choose startup mode before launching the local backend and dashboard.",
        "detail": "Select Local or Remote mode, then pick the startup profile.",
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
      .mode-actions {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin-top: 10px;
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
      .step-title {{
        margin: 0;
        color: #d8e6ff;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
      }}
      .selection-panel {{
        margin-top: 14px;
      }}
      .selection-panel[hidden] {{
        display: none;
      }}
      .profile-actions {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
      }}
      .profile-actions.remote {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
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
      .mode-button.active {{
        border-color: rgba(108, 199, 255, 0.46);
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
          <p class="profile-title">Startup Mode</p>
          <p class="step-title">Step 1: Select mode</p>
          <div class="mode-actions">
            <button id="mode-local" class="profile-button mode-button" type="button" onclick="window.__sstSwitchLaunchMode('local')">
              <strong>Local Mode</strong>
              <small>Run recognition and subtitles on this same PC.</small>
            </button>
            <button id="mode-remote" class="profile-button mode-button" type="button" onclick="window.__sstSwitchLaunchMode('remote')">
              <strong>Remote Mode</strong>
              <small>Use this PC as controller or processing worker in LAN mode.</small>
            </button>
          </div>
          <div id="selection-local" class="selection-panel">
            <p class="step-title">Step 2: Choose local startup profile</p>
            <div class="profile-actions">
              <button id="profile-browser" class="profile-button" data-mode="browser_google" type="button" onclick="window.__sstChooseLaunchOption('browser_google')">
                <strong>Quick Start (Browser Speech)</strong>
                <small>Fast startup. Uses browser speech worker and skips local AI runtime installation.</small>
              </button>
              <button id="profile-nvidia" class="profile-button" data-mode="nvidia" type="button" onclick="window.__sstChooseLaunchOption('nvidia')">
                <strong>Local AI (NVIDIA GPU)</strong>
                <small>Recommended for NVIDIA cards. Uses GPU-first runtime.</small>
              </button>
              <button id="profile-cpu" class="profile-button" data-mode="cpu" type="button" onclick="window.__sstChooseLaunchOption('cpu')">
                <strong>Local AI (CPU)</strong>
                <small>Use when CUDA GPU is unavailable.</small>
              </button>
            </div>
          </div>
          <div id="selection-remote" class="selection-panel" hidden>
            <p class="step-title">Step 2: Choose remote role</p>
            <div class="profile-actions remote">
              <button id="profile-remote-controller" class="profile-button" data-mode="remote_controller" type="button" onclick="window.__sstChooseLaunchOption('remote_controller')">
                <strong>Main PC (Control & Captions)</strong>
                <small>Sends microphone audio to remote AI worker and routes subtitles to local outputs.</small>
              </button>
              <button id="profile-remote-worker" class="profile-button" data-mode="remote_worker" type="button" onclick="window.__sstChooseLaunchOption('remote_worker')">
                <strong>AI Processing PC</strong>
                <small>Receives remote audio over WebRTC and runs recognition/translation.</small>
              </button>
            </div>
          </div>
          <p id="profile-hint" class="profile-hint">Choose mode and profile, then click the desired card to start.</p>
        </section>
        <section class="log-panel">
          <p class="log-title">Startup Dev Log</p>
          <textarea id="dev-log" readonly spellcheck="false">launcher: splash ready</textarea>
        </section>
        <div class="splash-footer">Powered by Kiriuru</div>
      `;
      const LOCAL_OPTIONS = ["browser_google", "nvidia", "cpu"];
      const REMOTE_OPTIONS = ["remote_controller", "remote_worker"];
      const MODE_DEFAULT_SELECTION = {{
        local: "nvidia",
        remote: "remote_controller",
      }};
      const launchState = {{
        mode: "local",
        selected: MODE_DEFAULT_SELECTION.local,
        locked: false,
      }};
      function inferModeFromSelection(selection) {{
        if (REMOTE_OPTIONS.includes(selection)) {{
          return "remote";
        }}
        return "local";
      }}
      function optionModeSet(mode) {{
        return mode === "remote" ? REMOTE_OPTIONS : LOCAL_OPTIONS;
      }}
      function renderLaunchState() {{
        const localPanel = document.getElementById("selection-local");
        const remotePanel = document.getElementById("selection-remote");
        if (localPanel) {{
          localPanel.hidden = launchState.mode !== "local";
        }}
        if (remotePanel) {{
          remotePanel.hidden = launchState.mode !== "remote";
        }}
        const modeLocal = document.getElementById("mode-local");
        const modeRemote = document.getElementById("mode-remote");
        if (modeLocal) {{
          modeLocal.classList.toggle("active", launchState.mode === "local");
          modeLocal.disabled = launchState.locked;
        }}
        if (modeRemote) {{
          modeRemote.classList.toggle("active", launchState.mode === "remote");
          modeRemote.disabled = launchState.locked;
        }}
        const allButtons = [
          document.getElementById("profile-browser"),
          document.getElementById("profile-nvidia"),
          document.getElementById("profile-cpu"),
          document.getElementById("profile-remote-controller"),
          document.getElementById("profile-remote-worker"),
        ];
        allButtons.forEach((button) => {{
          if (!button) return;
          const mode = String(button.dataset.mode || "").toLowerCase();
          button.classList.toggle("active", mode === launchState.selected);
          button.disabled = launchState.locked;
        }});
      }}
      window.__sstSwitchLaunchMode = function (mode) {{
        if (launchState.locked) {{
          return;
        }}
        const normalized = String(mode || "").toLowerCase() === "remote" ? "remote" : "local";
        launchState.mode = normalized;
        const validOptions = optionModeSet(normalized);
        if (!validOptions.includes(launchState.selected)) {{
          launchState.selected = MODE_DEFAULT_SELECTION[normalized];
        }}
        renderLaunchState();
      }};
      window.__sstSetLaunchOptionPrompt = function (payload) {{
        const normalized = payload || {{}};
        const hintEl = document.getElementById("profile-hint");
        const selected = String(normalized.selected || "").toLowerCase();
        const resolvedMode = String(normalized.mode || inferModeFromSelection(selected) || launchState.mode).toLowerCase() === "remote"
          ? "remote"
          : "local";
        launchState.mode = resolvedMode;
        launchState.locked = Boolean(normalized.locked);
        if (selected) {{
          launchState.selected = selected;
        }}
        const modeOptions = optionModeSet(launchState.mode);
        if (!modeOptions.includes(launchState.selected)) {{
          launchState.selected = MODE_DEFAULT_SELECTION[launchState.mode];
        }}
        if (hintEl) {{
          hintEl.textContent = normalized.hint || "Choose how this desktop session should start.";
        }}
        renderLaunchState();
      }};
      window.__sstChooseLaunchOption = function (selection) {{
        if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.choose_launch_mode !== "function") {{
          return;
        }}
        const normalized = String(selection || "").toLowerCase();
        const selectionMode = inferModeFromSelection(normalized);
        const applyingHint = normalized === "browser_google"
          ? "Applying Browser Speech quick start mode..."
          : normalized === "nvidia"
            ? "Applying local AI startup (NVIDIA GPU)..."
            : normalized === "cpu"
              ? "Applying local AI startup (CPU)..."
              : normalized === "remote_controller"
                ? "Applying remote mode: Main PC (Control & Captions)..."
                : "Applying remote mode: AI Processing PC...";
        window.__sstSetLaunchOptionPrompt({{ selected: normalized, mode: selectionMode, locked: true, hint: applyingHint }});
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
      window.__sstSetLaunchOptionPrompt({{
        selected: MODE_DEFAULT_SELECTION.local,
        mode: "local",
        locked: false,
        hint: "Choose mode and profile, then click the desired card to start.",
      }});
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


def _load_saved_remote_state(config_path: Path) -> tuple[bool, str]:
    if not config_path.exists():
        return False, REMOTE_ROLE_DISABLED
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return False, REMOTE_ROLE_DISABLED
    if not isinstance(payload, dict):
        return False, REMOTE_ROLE_DISABLED
    remote = payload.get("remote", {})
    if not isinstance(remote, dict):
        return False, REMOTE_ROLE_DISABLED
    enabled = bool(remote.get("enabled", False))
    role = normalize_remote_role(remote.get("role", REMOTE_ROLE_DISABLED))
    if enabled and role == REMOTE_ROLE_DISABLED:
        role = REMOTE_ROLE_CONTROLLER
    if not enabled:
        return False, REMOTE_ROLE_DISABLED
    return True, role


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
        config_path = self._paths.data_dir / "config.json"
        remote_enabled, remote_role = _load_saved_remote_state(config_path)
        return LaunchContext(
            desktop_mode=True,
            base_url=base_url,
            dashboard_url=f"{base_url}/?desktop=1",
            overlay_url=f"{base_url}/overlay",
            browser_worker_url=f"{base_url}/google-asr",
            startup_mode=_load_saved_asr_mode(config_path),
            install_profile=_read_install_profile(self._paths.install_profile_file),
            remote_role=remote_role if remote_enabled else REMOTE_ROLE_DISABLED,
            profile_name=_load_profile_name(config_path),
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
        selected_mode: str,
        saved_profile: str | None,
        detected_profile: str,
        saved_asr_mode: str,
        saved_remote_enabled: bool,
        saved_remote_role: str,
    ) -> None:
        selected_label = {
            LAUNCH_OPTION_BROWSER: "Quick Start (Browser Speech)",
            LAUNCH_OPTION_NVIDIA: "Local AI (NVIDIA GPU)",
            LAUNCH_OPTION_CPU: "Local AI (CPU)",
            LAUNCH_OPTION_REMOTE_CONTROLLER: "Main PC (Control & Captions)",
            LAUNCH_OPTION_REMOTE_WORKER: "AI Processing PC",
        }.get(selected, "Local AI (NVIDIA GPU)")
        detected_label = "NVIDIA GPU" if detected_profile == LAUNCH_OPTION_NVIDIA else "CPU"
        saved_mode_label = (
            "Remote mode"
            if saved_remote_enabled
            else "Browser Speech quick start"
            if saved_asr_mode == STARTUP_MODE_BROWSER
            else "Local AI"
        )
        if saved_remote_enabled:
            saved_mode_label = (
                "Remote worker (AI Processing PC)"
                if saved_remote_role == REMOTE_ROLE_WORKER
                else "Remote controller (Main PC)"
            )
        saved_install_label = saved_profile or detected_profile
        hint = (
            f"Choose mode and profile to continue startup. "
            f"Last saved startup: {saved_mode_label}. "
            f"Saved local install profile: {saved_install_label}. "
            f"Auto-detected local AI recommendation: {detected_label}. "
            f"Selected: {selected_label}."
        )
        payload = {"selected": selected, "mode": selected_mode, "hint": hint, "locked": False}
        try:
            window.evaluate_js(
                f"window.__sstSetLaunchOptionPrompt && window.__sstSetLaunchOptionPrompt({json.dumps(payload)});"
            )
        except Exception:
            pass

    def _wait_for_launch_option_selection(self, window: Any) -> tuple[str, str | None, str, bool]:
        config_path = self._paths.data_dir / "config.json"
        saved_profile = normalize_install_profile(_read_install_profile(self._paths.install_profile_file))
        detected_profile = auto_detect_install_profile()
        saved_asr_mode = _load_saved_asr_mode(config_path)
        saved_remote_enabled, saved_remote_role = _load_saved_remote_state(config_path)
        prefer_remote_default = saved_remote_enabled and saved_asr_mode != STARTUP_MODE_BROWSER
        if prefer_remote_default:
            selected = (
                LAUNCH_OPTION_REMOTE_WORKER
                if saved_remote_role == REMOTE_ROLE_WORKER
                else LAUNCH_OPTION_REMOTE_CONTROLLER
            )
            selected_mode = "remote"
        else:
            selected = LAUNCH_OPTION_BROWSER if saved_asr_mode == STARTUP_MODE_BROWSER else (saved_profile or detected_profile)
            selected_mode = "local"
        self._launch_option_event.clear()
        with self._selected_launch_option_lock:
            self._selected_launch_option = None
        self._publish_profile_prompt(
            window,
            selected=selected,
            selected_mode=selected_mode,
            saved_profile=saved_profile,
            detected_profile=detected_profile,
            saved_asr_mode=saved_asr_mode,
            saved_remote_enabled=saved_remote_enabled,
            saved_remote_role=saved_remote_role,
        )
        self._publish_window_status(
            window,
            "Choose Local or Remote mode on splash, then click a startup profile card to continue.",
        )
        self._publish_window_log(
            window,
            "launch selector ready: "
            f"saved_mode={saved_asr_mode}, "
            f"saved_remote={'on' if saved_remote_enabled else 'off'}:{saved_remote_role}, "
            f"remote_default={'on' if prefer_remote_default else 'off'}, "
            f"saved_install={saved_profile or 'none'}, detected={detected_profile}, selected={selected}",
        )
        while not self._launch_option_event.wait(timeout=0.2):
            if self._shutdown_started.is_set():
                raise RuntimeError("Desktop launcher was closed before the startup mode was selected.")
        chosen = self._selected_launch_mode() or selected
        if chosen == LAUNCH_OPTION_BROWSER:
            fallback_install_profile = saved_profile or detected_profile
            self._publish_window_status(window, "Preparing lightweight Browser Speech startup...")
            return STARTUP_MODE_BROWSER, fallback_install_profile, REMOTE_ROLE_DISABLED, False
        if chosen == LAUNCH_OPTION_REMOTE_CONTROLLER:
            self._publish_window_status(window, "Preparing remote controller startup (lightweight mode)...")
            return STARTUP_MODE_LOCAL, None, REMOTE_ROLE_CONTROLLER, False
        if chosen == LAUNCH_OPTION_REMOTE_WORKER:
            worker_profile = saved_profile or detected_profile
            worker_profile_label = "NVIDIA GPU" if worker_profile == LAUNCH_OPTION_NVIDIA else "CPU"
            self._publish_window_status(
                window,
                f"Preparing remote worker AI runtime ({worker_profile_label})...",
            )
            return STARTUP_MODE_LOCAL, worker_profile, REMOTE_ROLE_WORKER, True
        self._publish_window_status(
            window,
            "Preparing the local environment for NVIDIA GPU..." if chosen == LAUNCH_OPTION_NVIDIA else "Preparing the local CPU-only environment...",
        )
        return STARTUP_MODE_LOCAL, chosen, REMOTE_ROLE_DISABLED, False

    def _apply_startup_mode_to_config(
        self,
        startup_mode: str,
        install_profile: str | None,
        *,
        remote_role: str,
        remote_allow_lan: bool,
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

        normalized_remote_role = normalize_remote_role(remote_role, fallback=REMOTE_ROLE_DISABLED)
        if startup_mode == STARTUP_MODE_BROWSER:
            normalized_remote_role = REMOTE_ROLE_DISABLED
            remote_allow_lan = False
        if normalized_remote_role in {REMOTE_ROLE_CONTROLLER, REMOTE_ROLE_WORKER}:
            remote["enabled"] = True
            remote["role"] = normalized_remote_role
            if normalized_remote_role == REMOTE_ROLE_WORKER:
                lan["bind_enabled"] = bool(remote_allow_lan)
                lan["bind_host"] = "0.0.0.0" if remote_allow_lan else str(lan.get("bind_host", "127.0.0.1"))
            else:
                lan["bind_enabled"] = False
                lan["bind_host"] = "127.0.0.1"
        else:
            remote["enabled"] = False
            remote["role"] = REMOTE_ROLE_DISABLED
            lan["bind_enabled"] = False
        remote["lan"] = lan
        payload["remote"] = remote

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_log(
            "startup config applied: "
            f"mode={asr.get('mode')} "
            f"install_profile={install_profile or 'none'} "
            f"remote_role={normalized_remote_role} "
            f"remote_lan={'on' if remote_allow_lan else 'off'} "
            f"-> {config_path}"
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
        isolated_profile_dir = self._paths.runtime_root / "browser-worker-profile"
        try:
            isolated_profile_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._set_browser_worker_error(
                f"Failed to prepare browser worker profile directory '{isolated_profile_dir}': {type(exc).__name__}: {exc}"
            )
            return False
        args = [
            str(browser_path),
            "--new-window",
            "--no-first-run",
            "--disable-default-apps",
            f"--user-data-dir={isolated_profile_dir}",
            "--disable-session-crashed-bubble",
            "--window-size=980,860",
            normalized_url,
        ]
        self._write_log(f"[browser-worker] launch args: {args}")
        try:
            subprocess.Popen(
                args,
                cwd=str(browser_path.parent),
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            self._write_log(
                f"[browser-worker] launched isolated worker window via {browser_path}; profile={isolated_profile_dir}"
            )
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
        remote_role: str,
        remote_allow_lan: bool,
    ) -> None:
        bind_hint = "0.0.0.0 (LAN enabled)" if remote_allow_lan else "127.0.0.1"
        self._publish_window_status(window, f"Starting local backend subprocess on {bind_hint} ...")
        env["SST_REMOTE_ROLE"] = normalize_remote_role(remote_role, fallback=REMOTE_ROLE_DISABLED)
        env["SST_ALLOW_LAN"] = "1" if remote_allow_lan else "0"
        bootstrap_code = (
            "import runpy, sys; "
            f"sys.path.insert(0, {self._paths.bundle_root.as_posix()!r}); "
            "runpy.run_module('backend.run', run_name='__main__')"
        )
        args = [str(python_exe), "-u", "-c", bootstrap_code]
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
        self._publish_window_log(
            window,
            f"backend subprocess started via {python_exe} | remote_role={env['SST_REMOTE_ROLE']} | allow_lan={env['SST_ALLOW_LAN']}",
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

            startup_mode, install_profile_override, remote_role, remote_allow_lan = self._wait_for_launch_option_selection(window)
            bootstrapper = RuntimeBootstrapper(
                paths=self._paths,
                log=lambda message: self._publish_window_log(window, message),
                status=lambda message: self._publish_window_status(window, message),
                register_process=self._register_child_process,
                unregister_process=self._unregister_child_process,
            )
            install_profile = install_profile_override
            needs_local_ai_runtime = (
                startup_mode == STARTUP_MODE_LOCAL and remote_role != REMOTE_ROLE_CONTROLLER
            )
            if needs_local_ai_runtime:
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
                remote_allow_lan=remote_allow_lan,
            )
            self._context = LaunchContext(
                **{
                    **asdict(self._context),
                    "startup_mode": startup_mode,
                    "install_profile": install_profile or self._context.install_profile or "auto",
                    "remote_role": remote_role,
                    "profile_name": _load_profile_name(self._paths.data_dir / "config.json"),
                }
            )

            env = bootstrapper.runtime_environment()
            self._start_backend_process(
                window,
                python_exe,
                env,
                remote_role=remote_role,
                remote_allow_lan=remote_allow_lan,
            )
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
