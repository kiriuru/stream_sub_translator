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


APP_HOST = "127.0.0.1"
APP_PORT = 8765
APP_NAME = "Stream Subtitle Translator"
STARTUP_MODE_BROWSER = "browser_google"
STARTUP_MODE_LOCAL = "local"
DESKTOP_PROFILE_LOCK_BROWSER_SPEECH = "browser_speech"
LAUNCH_OPTION_BROWSER = "browser_google"
LAUNCH_OPTION_NVIDIA = "nvidia"
LAUNCH_OPTION_CPU = "cpu"
LAUNCH_OPTION_REMOTE_CONTROLLER = "remote_controller"
LAUNCH_OPTION_REMOTE_WORKER = "remote_worker"

UI_LAYOUT_STANDARD = "standard"
UI_LAYOUT_COMPACT = "compact"
SUPPORTED_UI_LANGUAGES = frozenset({"en", "ru"})

DASHBOARD_WINDOW_SIZES: dict[str, dict[str, int]] = {
    UI_LAYOUT_STANDARD: {"width": 1440, "height": 940, "min_width": 1180, "min_height": 760},
    UI_LAYOUT_COMPACT: {"width": 400, "height": 844, "min_width": 360, "min_height": 640},
}
# Fixed splash chrome — dashboard layout resize happens only after the dashboard loads.
SPLASH_WINDOW_DEFAULT = {"width": 700, "height": 540, "min_width": 700, "min_height": 540}
SPLASH_WINDOW_WEB_ONLY = {"width": 560, "height": 380, "min_width": 560, "min_height": 380}

_SPLASH_I18N: dict[str, dict[str, str]] = {
    "en": {
        "launcher.eyebrow": "Desktop Launcher",
        "launcher.subtitle": "Preparing the local runtime, backend, and dashboard window...",
        "launcher.subtitle.web_only": "Preparing Web Speech runtime, backend, and dashboard window...",
        "launcher.status.initial": "Choose Browser Speech, CPU, or GPU to continue. Remote modes are available under the secondary Remote block.",
        "launcher.status.web_only_initial": "Starting Web Speech mode. Preparing the lightweight runtime...",
        "launcher.profile.title": "Runtime Profile",
        "launcher.profile.hint_default": "Choose how this desktop session should start.",
        "launcher.profile.quick_start": "Quick Start",
        "launcher.profile.quick_start_hint": "Web Speech only. Opens the dashboard fast and skips local AI runtime installation.",
        "launcher.profile.nvidia": "NVIDIA GPU (CUDA)",
        "launcher.profile.nvidia_hint": "Recommended for NVIDIA cards. Uses the GPU-first PyTorch runtime.",
        "launcher.profile.cpu": "CPU-only",
        "launcher.profile.cpu_hint": "Recommended for AMD, Intel, or no-GPU machines.",
        "launcher.profile.remote_modes": "Remote modes",
        "launcher.profile.remote_controller": "Remote Controller",
        "launcher.profile.remote_controller_hint": "Lightweight controller session for pairing with a worker on your LAN.",
        "launcher.profile.remote_worker": "Remote Worker",
        "launcher.profile.remote_worker_hint": "Local AI worker session with LAN bind enabled for a controller.",
        "launcher.log.title": "Startup Dev Log",
        "launcher.footer": "Powered by Kiriuru",
        "language.label": "Interface language",
        "launcher.profile.applying_browser": "Applying the Browser Speech quick start mode...",
        "launcher.profile.applying_remote_controller": "Applying the remote controller startup mode...",
        "launcher.profile.applying_remote_worker": "Applying the remote worker startup mode...",
        "launcher.profile.applying_local": "Applying the selected local AI runtime profile...",
        "launcher.status.preparing_browser": "Preparing lightweight Browser Speech startup...",
        "launcher.status.preparing_remote_controller": "Preparing lightweight remote controller startup...",
        "launcher.status.preparing_remote_worker": "Preparing remote worker startup with {profile} local AI...",
        "launcher.status.preparing_nvidia": "Preparing the local environment for NVIDIA GPU...",
        "launcher.status.preparing_cpu": "Preparing the local CPU-only environment...",
        "launcher.status.backend_starting": "Starting local backend subprocess on 127.0.0.1 ...",
        "launcher.status.health_wait": "Waiting for local /api/health ...",
        "launcher.status.backend_ready": "Backend ready. Loading dashboard...",
    },
    "ru": {
        "launcher.eyebrow": "Запуск desktop",
        "launcher.subtitle": "Подготовка локального runtime, backend и окна дашборда...",
        "launcher.subtitle.web_only": "Подготовка Web Speech runtime, backend и окна дашборда...",
        "launcher.status.initial": "Выберите Browser Speech, CPU или GPU. Режимы Remote — в блоке ниже.",
        "launcher.status.web_only_initial": "Запуск режима Web Speech. Подготовка лёгкого runtime...",
        "launcher.profile.title": "Профиль запуска",
        "launcher.profile.hint_default": "Выберите, как должна стартовать эта desktop-сессия.",
        "launcher.profile.quick_start": "Быстрый старт",
        "launcher.profile.quick_start_hint": "Только Web Speech. Быстро открывает дашборд без установки локального AI runtime.",
        "launcher.profile.nvidia": "NVIDIA GPU (CUDA)",
        "launcher.profile.nvidia_hint": "Рекомендуется для видеокарт NVIDIA. GPU-first PyTorch runtime.",
        "launcher.profile.cpu": "Только CPU",
        "launcher.profile.cpu_hint": "Рекомендуется для AMD, Intel или ПК без GPU.",
        "launcher.profile.remote_modes": "Remote-режимы",
        "launcher.profile.remote_controller": "Remote Controller",
        "launcher.profile.remote_controller_hint": "Облегчённая controller-сессия для pairing с worker в LAN.",
        "launcher.profile.remote_worker": "Remote Worker",
        "launcher.profile.remote_worker_hint": "Локальный AI worker с LAN bind для controller.",
        "launcher.log.title": "Лог запуска (dev)",
        "launcher.footer": "Powered by Kiriuru",
        "language.label": "Язык интерфейса",
        "launcher.profile.applying_browser": "Применяется быстрый старт Browser Speech...",
        "launcher.profile.applying_remote_controller": "Применяется режим remote controller...",
        "launcher.profile.applying_remote_worker": "Применяется режим remote worker...",
        "launcher.profile.applying_local": "Применяется выбранный профиль локального AI...",
        "launcher.status.preparing_browser": "Подготовка лёгкого запуска Browser Speech...",
        "launcher.status.preparing_remote_controller": "Подготовка лёгкого remote controller...",
        "launcher.status.preparing_remote_worker": "Подготовка remote worker с локальным AI ({profile})...",
        "launcher.status.preparing_nvidia": "Подготовка локального окружения для NVIDIA GPU...",
        "launcher.status.preparing_cpu": "Подготовка локального CPU-only окружения...",
        "launcher.status.backend_starting": "Запуск локального backend на 127.0.0.1 ...",
        "launcher.status.health_wait": "Ожидание /api/health ...",
        "launcher.status.backend_ready": "Backend готов. Загрузка дашборда...",
    },
}

_BROWSER_WORKER_PATHS = frozenset(
    {
        "/google-asr",
        "/google-asr-experimental",
    }
)
_BROWSER_WORKER_EXPERIMENTAL_PATHS = frozenset({"/google-asr-experimental"})


class LaunchSelectionCancelled(Exception):
    """The user closed the desktop window before choosing a startup mode."""


def _show_error_dialog(title: str, message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        print(f"{title}: {message}")


def _normalize_ui_language(value: str | None) -> str:
    current = str(value or "").strip().lower()
    return "ru" if current == "ru" else "en"


def _load_ui_language(config_path: Path) -> str:
    if not config_path.exists():
        return "en"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return "en"
    ui = payload.get("ui", {}) if isinstance(payload, dict) else {}
    if not isinstance(ui, dict):
        return "en"
    return _normalize_ui_language(ui.get("language"))


def _save_ui_language(config_path: Path, locale: str) -> None:
    normalized = _normalize_ui_language(locale)
    payload: dict[str, Any]
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
            payload = existing if isinstance(existing, dict) else {}
        except Exception:
            payload = {}
    else:
        payload = {}
    ui = payload.get("ui", {})
    if not isinstance(ui, dict):
        ui = {}
    ui["language"] = normalized
    payload["ui"] = ui
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_ui_layout(config_path: Path) -> str:
    if not config_path.exists():
        return UI_LAYOUT_STANDARD
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return UI_LAYOUT_STANDARD
    ui = payload.get("ui", {}) if isinstance(payload, dict) else {}
    if not isinstance(ui, dict):
        return UI_LAYOUT_STANDARD
    layout = str(ui.get("layout", UI_LAYOUT_STANDARD) or UI_LAYOUT_STANDARD).strip().lower()
    return UI_LAYOUT_COMPACT if layout == UI_LAYOUT_COMPACT else UI_LAYOUT_STANDARD


def _splash_t(locale: str, key: str, **variables: str) -> str:
    normalized = _normalize_ui_language(locale)
    catalog = _SPLASH_I18N.get(normalized, _SPLASH_I18N["en"])
    template = catalog.get(key) or _SPLASH_I18N["en"].get(key, key)
    if not variables:
        return template
    try:
        return template.format(**variables)
    except Exception:
        return template


def _splash_profile_hint(
    locale: str,
    *,
    selected: str,
    saved_profile: str | None,
    detected_profile: str,
    saved_asr_mode: str,
) -> str:
    if locale == "ru":
        saved_mode_label = "Browser Speech" if saved_asr_mode == STARTUP_MODE_BROWSER else "локальный AI"
        detected_label = "NVIDIA GPU" if detected_profile == "nvidia" else "CPU-only"
        profile_value = saved_profile or detected_profile
        selected_label = {
            LAUNCH_OPTION_BROWSER: "Быстрый старт (Browser Speech)",
            LAUNCH_OPTION_NVIDIA: "NVIDIA GPU (CUDA 12.8)",
            LAUNCH_OPTION_REMOTE_CONTROLLER: "Remote Controller",
            LAUNCH_OPTION_REMOTE_WORKER: "Remote Worker",
        }.get(selected, "Только CPU")
        saved_word = "сохранённый" if saved_profile else "автоопределённый"
        return (
            f"Выберите режим запуска. Сохранённый ASR: {saved_mode_label}. "
            f"Текущий {saved_word} профиль AI: {profile_value}. "
            f"Рекомендация AI: {detected_label}. Remote — во вторичном блоке. Выбрано: {selected_label}."
        )
    saved_mode_label = "Browser Speech quick start" if saved_asr_mode == STARTUP_MODE_BROWSER else "Local AI"
    detected_label = "NVIDIA GPU" if detected_profile == "nvidia" else "CPU-only"
    selected_label = {
        LAUNCH_OPTION_BROWSER: "Quick Start (Browser Speech)",
        LAUNCH_OPTION_NVIDIA: "NVIDIA GPU (CUDA 12.8)",
        LAUNCH_OPTION_REMOTE_CONTROLLER: "Remote Controller",
        LAUNCH_OPTION_REMOTE_WORKER: "Remote Worker",
    }.get(selected, "CPU-only")
    saved_word = "saved" if saved_profile else "detected"
    profile_value = saved_profile or detected_profile
    return (
        f"Choose how this desktop session should start. "
        f"Saved recognition mode: {saved_mode_label}. "
        f"Current {saved_word} local AI profile: {profile_value}. "
        f"Auto-detected local AI recommendation: {detected_label}. "
        f"Remote modes stay secondary and use LAN pairing when selected. "
        f"Selected: {selected_label}."
    )


def _resize_pywebview_window(window: Any, *, width: int, height: int, min_width: int, min_height: int) -> None:
    # min_size must be lowered before shrinking (e.g. standard 1180 -> compact 400).
    try:
        window.min_size = (int(min_width), int(min_height))
    except Exception:
        pass
    try:
        window.resize(int(width), int(height))
    except Exception:
        pass


def _build_splash_html(title: str, *, locale: str, web_speech_only: bool = False) -> str:
    return build_splash_html(
        title,
        locale=locale,
        translations=_SPLASH_I18N,
        web_speech_only=web_speech_only,
    )


@dataclass(frozen=True)
class LaunchContext:
    desktop_mode: bool
    base_url: str
    dashboard_url: str
    overlay_url: str
    browser_worker_url: str
    worker_launch_browser: str
    startup_mode: str
    web_speech_only: bool
    install_profile: str
    remote_role: str
    profile_name: str
    project_root: str
    data_dir: str


def _load_worker_launch_browser_preference(config_path: Path) -> str:
    allowed = {"auto", "google_chrome"}
    default = "auto"
    if not config_path.exists():
        return default
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return default
    asr = payload.get("asr", {}) if isinstance(payload, dict) else {}
    if not isinstance(asr, dict):
        return default
    browser = asr.get("browser", {})
    if not isinstance(browser, dict):
        return default
    raw = str(browser.get("worker_launch_browser", default) or default).strip().lower()
    if raw == "chromium":
        raw = default
    if raw == "microsoft_edge":
        raw = "google_chrome"
    return raw if raw in allowed else default


def ordered_browser_executable_names(_launch_preference: str) -> tuple[str, ...]:
    return ("chrome.exe",)


def _classic_browser_worker_path_for_preference(_worker_launch_browser: str) -> str:
    return "/google-asr"


def _filesystem_relative_candidates_for_exes(ordered_exes: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    parts_by_exe: dict[str, tuple[str, ...]] = {
        "chrome.exe": ("Google", "Chrome", "Application", "chrome.exe"),
    }
    out: list[tuple[str, ...]] = []
    for name in ordered_exes:
        rel = parts_by_exe.get(name)
        if rel:
            out.append(rel)
    return tuple(out)


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


def _load_saved_remote_startup(config_path: Path) -> tuple[str, bool]:
    if not config_path.exists():
        return "disabled", False
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return "disabled", False
    remote = payload.get("remote", {}) if isinstance(payload, dict) else {}
    if not isinstance(remote, dict):
        return "disabled", False
    role = str(remote.get("role", "disabled") or "disabled").strip().lower()
    if role not in {"disabled", "controller", "worker"}:
        role = "disabled"
    lan = remote.get("lan", {})
    allow_lan = bool(isinstance(lan, dict) and lan.get("bind_enabled"))
    return role, allow_lan


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
        window_getter: callable,
    ) -> None:
        self._context_getter = context_getter
        self._external_url_opener = external_url_opener
        self._launch_mode_selector = launch_mode_selector
        self._window_getter = window_getter

    def _config_path(self) -> Path:
        data_dir = str(self._context_getter().data_dir or "").strip()
        return Path(data_dir) / "config.json" if data_dir else Path("config.json")

    def get_launch_context(self) -> dict[str, Any]:
        payload = asdict(self._context_getter())
        payload["pywebview_gui"] = os.environ.get("PYWEBVIEW_GUI", "edgechromium")
        try:
            paths = detect_runtime_paths()
            payload["pywebview_storage_path"] = str(paths.runtime_root / "pywebview-profile")
        except Exception:
            payload["pywebview_storage_path"] = ""
        data_dir = str(payload.get("data_dir") or "").strip()
        if data_dir:
            cfg = Path(data_dir) / "config.json"
            worker_browser = _load_worker_launch_browser_preference(cfg)
            payload["worker_launch_browser"] = worker_browser
            base = str(payload.get("base_url") or "").rstrip("/")
            if base:
                payload["browser_worker_url"] = base + _classic_browser_worker_path_for_preference(worker_browser)
        return payload

    def open_external_url(self, url: str) -> bool:
        return bool(self._external_url_opener(str(url or "").strip()))

    def choose_launch_mode(self, selection: str) -> bool:
        return bool(self._launch_mode_selector(str(selection or "").strip()))

    def request_runtime_start(
        self,
        device_id: str | None = None,
        config_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /api/runtime/start from the desktop shell (bypasses pywebview fetch quirks)."""
        base_url = str(self._context_getter().base_url or f"http://{APP_HOST}:{APP_PORT}").rstrip("/")
        url = f"{base_url}/api/runtime/start"
        body_obj: dict[str, Any] = {
            "device_id": device_id,
            "config_payload": config_payload if isinstance(config_payload, dict) else None,
        }
        timeout_seconds = 600.0
        if isinstance(config_payload, dict):
            asr = config_payload.get("asr")
            mode = str(asr.get("mode") if isinstance(asr, dict) else "").strip().lower()
            if mode in {STARTUP_MODE_BROWSER, "browser_google_experimental"}:
                timeout_seconds = 120.0
        try:
            request = Request(
                url,
                data=json.dumps(body_obj, ensure_ascii=False).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=timeout_seconds) as response:
                status = int(getattr(response, "status", 0) or 0)
                body_text = response.read().decode("utf-8", errors="replace")
            payload: dict[str, Any] = {}
            if body_text.strip():
                try:
                    parsed = json.loads(body_text)
                    if isinstance(parsed, dict):
                        payload = parsed
                except json.JSONDecodeError:
                    payload = {"raw": body_text[:2000]}
            return {"ok": 200 <= status < 300, "status": status, "payload": payload}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def request_runtime_stop(self) -> dict[str, Any]:
        """POST /api/runtime/stop from the desktop shell (bypasses pywebview fetch quirks)."""
        base_url = str(self._context_getter().base_url or f"http://{APP_HOST}:{APP_PORT}").rstrip("/")
        url = f"{base_url}/api/runtime/stop"
        try:
            request = Request(url, data=b"{}", method="POST")
            with urlopen(request, timeout=120.0) as response:
                status = int(getattr(response, "status", 0) or 0)
                body_text = response.read().decode("utf-8", errors="replace")
            payload: dict[str, Any] = {}
            if body_text.strip():
                try:
                    parsed = json.loads(body_text)
                    if isinstance(parsed, dict):
                        payload = parsed
                except json.JSONDecodeError:
                    payload = {"raw": body_text[:2000]}
            return {"ok": 200 <= status < 300, "status": status, "payload": payload}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def get_ui_language(self) -> str:
        return _load_ui_language(self._config_path())

    def set_ui_language(self, locale: str) -> str:
        normalized = _normalize_ui_language(locale)
        _save_ui_language(self._config_path(), normalized)
        window = self._window_getter()
        if window is not None:
            try:
                window.evaluate_js(
                    f"window.__sstApplySplashLocale && window.__sstApplySplashLocale({json.dumps(normalized)});"
                )
            except Exception:
                pass
        return normalized

    def fit_splash_window(self, width: int, height: int) -> bool:
        window = self._window_getter()
        if window is None:
            return False
        safe_width = max(SPLASH_WINDOW_DEFAULT["min_width"], min(int(width), 900))
        safe_height = max(SPLASH_WINDOW_DEFAULT["min_height"], min(int(height), 780))
        try:
            window.resize(safe_width, safe_height)
            return True
        except Exception:
            return False

    def resize_main_window(
        self,
        layout: str,
        width: int,
        height: int,
        min_width: int,
        min_height: int,
    ) -> bool:
        window = self._window_getter()
        if window is None:
            return False
        _resize_pywebview_window(
            window,
            width=int(width),
            height=int(height),
            min_width=int(min_width),
            min_height=int(min_height),
        )
        ui_trace(
            "desktop",
            "pywebview",
            "resize_main_window",
            layout=str(layout),
            width=int(width),
            height=int(height),
            min_width=int(min_width),
            min_height=int(min_height),
        )
        return True


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


def _wait_for_http_ok(
    url: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: float = 0.35,
    abort_if: callable | None = None,
    on_retry: callable | None = None,
) -> None:
    """Wait until the local HTTP server answers (dashboard HTML), without full health JSON."""
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
            with urlopen(url, timeout=3) as response:
                status = int(getattr(response, "status", 200))
                if 200 <= status < 400:
                    return
                raise RuntimeError(f"HTTP {status}")
        except Exception as exc:
            last_error = str(exc)
            if on_retry is not None:
                on_retry(attempt, last_error)
            time.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"Local server did not become ready within {timeout_seconds}s. "
        f"Last error: {last_error or 'unknown'}"
    )


RUNTIME_METRICS_LOG_PREFIX = "[runtime-metrics]"
RUNTIME_METRICS_POLL_ACTIVE_SECONDS = 5.0
RUNTIME_METRICS_POLL_IDLE_SECONDS = 30.0
RUNTIME_METRICS_FROZEN_WARN_SECONDS = 30.0
_RUNTIME_METRICS_ACTIVE_STATUSES = frozenset(
    {"starting", "listening", "transcribing", "translating", "error"},
)
_RUNTIME_METRICS_PROGRESS_KEYS = (
    "vad_segments_partial",
    "vad_segments_final",
    "asr_queue_depth",
    "partial_updates_emitted",
    "finals_emitted",
    "in_flight_transcribe_count",
    "vad_dropped_segments",
)


def _fetch_json_object(url: str, *, timeout_seconds: float = 3.0) -> dict[str, Any] | None:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _runtime_status_value(payload: dict[str, Any]) -> str:
    return str(payload.get("status") or payload.get("phase") or "unknown")


def _runtime_metrics_dict(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _runtime_asr_diagnostics_dict(payload: dict[str, Any]) -> dict[str, Any]:
    asr_diagnostics = payload.get("asr_diagnostics")
    if isinstance(asr_diagnostics, dict):
        return asr_diagnostics
    asr = payload.get("asr")
    if isinstance(asr, dict):
        nested = asr.get("diagnostics")
        if isinstance(nested, dict):
            return nested
    return {}


def _runtime_audio_device_label(payload: dict[str, Any]) -> str:
    diagnostics = _runtime_asr_diagnostics_dict(payload)
    for key in ("requested_device", "selected_device", "device_active"):
        value = diagnostics.get(key)
        if value not in (None, ""):
            return str(value)
    return "none"


def _runtime_metrics_progress_signature(payload: dict[str, Any]) -> tuple[int, ...]:
    metrics = _runtime_metrics_dict(payload)
    return tuple(int(metrics.get(key, 0) or 0) for key in _RUNTIME_METRICS_PROGRESS_KEYS)


def _runtime_capture_sample_rate(payload: dict[str, Any]) -> str:
    diagnostics = _runtime_asr_diagnostics_dict(payload)
    for key in ("capture_sample_rate", "sample_rate"):
        value = diagnostics.get(key)
        if value not in (None, ""):
            return str(value)
    return "none"


def _runtime_model_loaded(payload: dict[str, Any]) -> str:
    diagnostics = _runtime_asr_diagnostics_dict(payload)
    if "model_loaded" in diagnostics:
        return str(bool(diagnostics.get("model_loaded")))
    return "unknown"


def _runtime_execution_device(payload: dict[str, Any]) -> str:
    diagnostics = _runtime_asr_diagnostics_dict(payload)
    for key in ("device_active", "selected_device", "actual_execution_provider"):
        value = diagnostics.get(key)
        if value not in (None, ""):
            return str(value)
    return "none"


def _format_runtime_metrics_log_line(payload: dict[str, Any]) -> str:
    status = _runtime_status_value(payload)
    metrics = _runtime_metrics_dict(payload)
    device = _runtime_audio_device_label(payload)
    parts = [
        f"status={status}",
        f"device={device}",
        f"capture_sr={_runtime_capture_sample_rate(payload)}",
        f"model_loaded={_runtime_model_loaded(payload)}",
        f"exec_device={_runtime_execution_device(payload)}",
        f"vad_partial={int(metrics.get('vad_segments_partial', 0) or 0)}",
        f"vad_final={int(metrics.get('vad_segments_final', 0) or 0)}",
        f"asr_queue={int(metrics.get('asr_queue_depth', 0) or 0)}",
        f"partials={int(metrics.get('partial_updates_emitted', 0) or 0)}",
        f"finals={int(metrics.get('finals_emitted', 0) or 0)}",
        f"in_flight={int(metrics.get('in_flight_transcribe_count', 0) or 0)}",
        f"vad_dropped={int(metrics.get('vad_dropped_segments', 0) or 0)}",
    ]
    last_error = payload.get("last_error")
    if last_error:
        parts.append(f"error={last_error}")
    return f"{RUNTIME_METRICS_LOG_PREFIX} " + " ".join(parts)


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

    def _current_ui_language(self) -> str:
        return _load_ui_language(self._paths.data_dir / "config.json")

    def _resize_window_for_dashboard(self, window: Any, layout: str | None = None) -> str:
        resolved = layout or _load_ui_layout(self._paths.data_dir / "config.json")
        sizes = DASHBOARD_WINDOW_SIZES.get(resolved, DASHBOARD_WINDOW_SIZES[UI_LAYOUT_STANDARD])
        _resize_pywebview_window(
            window,
            width=sizes["width"],
            height=sizes["height"],
            min_width=sizes["min_width"],
            min_height=sizes["min_height"],
        )
        return resolved

    def _should_publish_splash_dom_updates(self) -> bool:
        return bool(self._splash_shell_active) and not self._shutdown_started.is_set()

    def _dashboard_location_url(self, window: Any) -> str:
        try:
            href = window.evaluate_js("window.location.href")
            if href:
                return str(href).strip()
        except Exception:
            pass
        return str(
            getattr(window, "real_url", None) or getattr(window, "original_url", None) or ""
        ).strip()

    def _apply_dashboard_resize(self, window: Any, *, trigger: str) -> bool:
        if self._shutdown_started.is_set() or self._dashboard_resize_done:
            return False
        try:
            layout = self._resize_window_for_dashboard(window)
            self._dashboard_resize_done = True
            self._write_log(f"dashboard window resized ({trigger}): layout={layout}")
            ui_trace("desktop", "pywebview", "dashboard_resize_complete", trigger=trigger, layout=layout)
            return True
        except Exception as exc:
            self._write_log(
                f"dashboard resize failed ({trigger}): {type(exc).__name__}: {exc}"
            )
            ui_trace(
                "desktop",
                "pywebview",
                "dashboard_resize_failed",
                trigger=trigger,
                error=f"{type(exc).__name__}: {exc}",
            )
            return False

    def _navigate_to_dashboard(self, window: Any, url: str) -> None:
        """Navigate to the dashboard via load_url so pywebview re-injects the JS bridge API.

        load_url is the pywebview-native navigation method: it triggers a full page load where
        the JS bridge (window.pywebview.api) is correctly injected into the destination page.
        window.location.replace() via evaluate_js caused the JS bridge to be unavailable in the
        new page, resulting in desktop_mode being reported as false and pywebview API calls failing.
        """
        self._splash_shell_active = False
        self._dashboard_navigation_started = True
        target = str(url or "").strip()
        ui_trace(
            "desktop",
            "pywebview",
            "dashboard_navigation_begin",
            method="load_url",
            target_url=target,
        )
        try:
            window.load_url(target)
            self._write_log(f"dashboard navigation via load_url: {target}")
            ui_trace("desktop", "pywebview", "dashboard_navigation_complete", method="load_url", target_url=target)
        except Exception as exc:
            self._write_log(
                f"dashboard load_url failed ({type(exc).__name__}: {exc}), "
                f"falling back to location.replace"
            )
            ui_trace(
                "desktop",
                "pywebview",
                "dashboard_navigation_failed",
                method="load_url",
                target_url=target,
                error=f"{type(exc).__name__}: {exc}",
            )
            try:
                window.evaluate_js(f"window.location.replace({json.dumps(target)});")
                self._write_log(f"dashboard navigation via location.replace (fallback): {target}")
                ui_trace(
                    "desktop",
                    "pywebview",
                    "dashboard_navigation_complete",
                    method="location_replace",
                    target_url=target,
                )
            except Exception as exc2:
                self._write_log(
                    f"dashboard navigation fallback also failed: {type(exc2).__name__}: {exc2}"
                )
        self._schedule_dashboard_resize(window)

    def _schedule_dashboard_resize(self, window: Any) -> None:
        max_attempts = 180

        def attempt(remaining: int = max_attempts) -> None:
            if self._shutdown_started.is_set() or self._dashboard_resize_done:
                return
            current_url = self._dashboard_location_url(window)
            if "desktop=1" not in current_url:
                if remaining > 0:
                    if remaining == max_attempts or remaining % 20 == 0:
                        self._write_log(
                            f"dashboard resize waiting for desktop=1 url "
                            f"(attempts_left={remaining}, current_url={current_url or 'empty'})"
                        )
                    threading.Timer(0.35, lambda: attempt(remaining - 1)).start()
                elif self._dashboard_navigation_started:
                    self._apply_dashboard_resize(window, trigger="navigation fallback")
                else:
                    self._write_log(
                        "dashboard resize skipped: url never reached desktop=1 within "
                        f"{max_attempts * 0.35:.0f}s (last_url={current_url or 'empty'})"
                    )
                return
            self._apply_dashboard_resize(window, trigger="dashboard url detected")

        threading.Timer(0.25, lambda: attempt()).start()

    def _on_desktop_window_loaded(self, window: Any) -> None:
        if self._shutdown_started.is_set() or self._dashboard_resize_done:
            return
        current_url = self._dashboard_location_url(window)
        ui_trace(
            "desktop",
            "pywebview",
            "window_loaded",
            current_url=current_url or None,
            dashboard_ready="desktop=1" in (current_url or ""),
        )
        if "desktop=1" not in current_url:
            return
        self._apply_dashboard_resize(window, trigger="loaded event")

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

    def _publish_window_log(self, window: Any, message: str) -> None:
        self._write_log(message)
        if not self._should_publish_splash_dom_updates():
            return
        try:
            window.evaluate_js(f"window.__sstDesktopLog && window.__sstDesktopLog({json.dumps(message)});")
        except Exception:
            pass

    def _publish_window_status(
        self,
        window: Any,
        message: str = "",
        *,
        status_key: str | None = None,
    ) -> None:
        locale = self._current_ui_language()
        if status_key:
            resolved = _splash_t(locale, status_key)
            self._write_log(f"status: {resolved}")
            ui_trace("desktop", "splash", "status", status_key=status_key, message=resolved)
            if self._should_publish_splash_dom_updates():
                try:
                    window.evaluate_js(
                        f"window.__sstDesktopStatus && window.__sstDesktopStatus('', {json.dumps(status_key)});"
                    )
                except Exception:
                    pass
            return
        self._write_log(f"status: {message}")
        ui_trace("desktop", "splash", "status", message=message)
        if not self._should_publish_splash_dom_updates():
            return
        try:
            window.evaluate_js(f"window.__sstDesktopStatus && window.__sstDesktopStatus({json.dumps(message)});")
        except Exception:
            pass

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
        return resolved.name.lower() == "chrome.exe"

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

    def _find_chromium_browser(self, launch_preference: str | None = None) -> Path | None:
        preference = str(launch_preference or "").strip().lower() or _load_worker_launch_browser_preference(
            self._paths.data_dir / "config.json"
        )
        candidate_names = ordered_browser_executable_names(preference)
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
        relative_candidates = _filesystem_relative_candidates_for_exes(candidate_names)
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
            path = urlparse(normalized_url).path.rstrip("/").lower()
            return path in _BROWSER_WORKER_PATHS
        except Exception:
            return False

    def _browser_worker_uses_isolated_profile(self, _browser_path: Path) -> bool:
        """Browser Speech worker always uses an isolated Chromium profile directory (Chrome only)."""
        return True

    def _browser_worker_profile_dir(self, normalized_url: str, browser_path: Path) -> Path:
        """Isolated Chromium profile root for the external worker window.

        Classic vs experimental use different directories (mode switch safety).
        """
        try:
            path = urlparse(normalized_url).path.rstrip("/").lower()
        except Exception:
            path = ""
        variant = "experimental" if path in _BROWSER_WORKER_EXPERIMENTAL_PATHS else "classic"
        engine = (browser_path.stem or "chromium").lower()
        safe_engine = "".join(ch for ch in engine if ch.isalnum() or ch in "-_") or "chromium"
        return self._paths.runtime_root / f"browser-worker-profile-{variant}-{safe_engine}"

    def _open_browser_worker_window(self, normalized_url: str) -> bool:
        self._browser_worker_last_error = None
        preference = _load_worker_launch_browser_preference(self._paths.data_dir / "config.json")
        browser_path = self._find_chromium_browser(preference)
        if browser_path is None:
            self._set_browser_worker_error(
                "Could not find a usable Google Chrome executable for Browser Speech worker launch."
            )
            _show_error_dialog(
                f"{APP_NAME} Browser Speech Error",
                "Could not find Google Chrome for Browser Speech.\n\n"
                f"See launcher log:\n{self._log_path}",
            )
            return False
        use_isolated_profile = self._browser_worker_uses_isolated_profile(browser_path)
        isolated_profile_dir: Path | None = None
        if use_isolated_profile:
            isolated_profile_dir = self._browser_worker_profile_dir(normalized_url, browser_path)
            try:
                isolated_profile_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self._set_browser_worker_error(
                    f"Failed to prepare browser worker profile directory '{isolated_profile_dir}': {type(exc).__name__}: {exc}"
                )
                return False
        # Chrome feature gates that have historically interfered with Web Speech stability
        # when the worker window is partially covered (OBS preview, dashboard on top),
        # the OS is throttling background work, or Chrome attempts to suspend the tab.
        # Keep this list audited; removing entries usually re-introduces "Web Speech goes
        # quiet when OBS covers the window" or "tab discarded after a few minutes" bugs.
        disabled_chrome_features = (
            "CalculateNativeWinOcclusion",
            "HighEfficiencyModeAvailable",
            "HeuristicMemorySaver",
            "IntensiveWakeUpThrottling",
            "GlobalMediaControls",
        )
        args = [
            str(browser_path),
            "--new-window",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
        ]
        if use_isolated_profile and isolated_profile_dir is not None:
            args.append(f"--user-data-dir={isolated_profile_dir}")
        args.extend(
            [
                "--disable-session-crashed-bubble",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
                "--disable-features=" + ",".join(disabled_chrome_features),
                "--noerrdialogs",
                "--window-size=980,860",
                normalized_url,
            ]
        )
        self._write_log(f"[browser-worker] launch args: {args}")
        creation_flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "HIGH_PRIORITY_CLASS", 0x00000080)
        )
        try:
            popen = logged_popen(
                "browser_worker",
                args,
                cwd=str(browser_path.parent),
                creationflags=creation_flags,
                watch_exit=True,
                extra={"browser_path": str(browser_path), "profile_dir": str(isolated_profile_dir or "")},
            )
            self._write_log(
                f"[browser-worker] launched isolated worker window with address bar via {browser_path}; "
                f"profile={isolated_profile_dir}; pid={popen.pid}; priority=HIGH_PRIORITY_CLASS"
            )
            self._register_child_process(popen, role="browser_worker")
            self._opt_out_chrome_power_throttling(popen.pid)
            return True
        except Exception as exc:
            self._set_browser_worker_error(
                f"Failed to launch Browser Speech worker via {browser_path}: {type(exc).__name__}: {exc}"
            )
            _show_error_dialog(
                f"{APP_NAME} Browser Speech Error",
                "Browser Speech could not open the dedicated Chrome worker window.\n\n"
                f"Reason: {type(exc).__name__}: {exc}\n\n"
                f"See launcher log:\n{self._log_path}",
            )
            return False

    def _opt_out_chrome_power_throttling(self, pid: int) -> None:
        """Best-effort: opt the Chrome worker process out of Windows 11 EcoQoS / Efficiency Mode.

        Without this, on Windows 11 the OS can place the process into Efficiency Mode when the
        window is in the background or partially covered, which throttles JS timers and audio
        callbacks and causes the Web Speech worker to silently stop emitting partials.

        Uses SetProcessInformation with ProcessPowerThrottling (Win32 API, since Win 10 1709).
        Documented as the official mechanism for processes that must keep full execution speed
        regardless of foreground state.
        """
        if os.name != "nt":
            return
        if not pid:
            return
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_SET_INFORMATION = 0x0200
            ProcessPowerThrottling = 4  # PROCESS_INFORMATION_CLASS enumeration value
            PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
            PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1

            class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
                _fields_ = [
                    ("Version", wintypes.ULONG),
                    ("ControlMask", wintypes.ULONG),
                    ("StateMask", wintypes.ULONG),
                ]

            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.SetProcessInformation.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            kernel32.SetProcessInformation.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL

            handle = kernel32.OpenProcess(PROCESS_SET_INFORMATION, False, int(pid))
            if not handle:
                self._write_log(
                    f"[browser-worker] power-throttling opt-out skipped: could not open process pid={pid}"
                )
                return
            try:
                state = PROCESS_POWER_THROTTLING_STATE()
                state.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
                state.ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED
                state.StateMask = 0  # 0 = OPT OUT (do NOT throttle execution speed)
                ok = kernel32.SetProcessInformation(
                    handle,
                    ProcessPowerThrottling,
                    ctypes.byref(state),
                    ctypes.sizeof(state),
                )
                if ok:
                    self._write_log(
                        f"[browser-worker] power-throttling opt-out applied for pid={pid} (Windows EcoQoS disabled)"
                    )
                else:
                    last_err = ctypes.get_last_error() if hasattr(ctypes, "get_last_error") else None
                    self._write_log(
                        f"[browser-worker] power-throttling opt-out call returned 0 for pid={pid} (last_error={last_err})"
                    )
            finally:
                kernel32.CloseHandle(handle)
        except Exception as exc:
            self._write_log(
                f"[browser-worker] power-throttling opt-out failed for pid={pid}: {type(exc).__name__}: {exc}"
            )

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

    def bootstrap(self, window: Any) -> None:
        try:
            from desktop.deps_install_trace import configure_deps_install_trace

            # Deep traces (startup-journey, ui-trace, api-trace) are opt-in via
            # SST_DEEP_DIAGNOSTICS / SST_TRACE_* — keep desktop launcher in sync
            # with the backend gate (`backend/core/app_bootstrap.py`) so the same
            # files are produced (or skipped) regardless of whether the user
            # started via start.bat or the desktop launcher.
            if is_startup_journey_enabled():
                configure_startup_journey_log(self._paths.project_root / "logs")
            # deps-install-trace and subprocess-trace are always-on per
            # docs/ETALON_RUNTIME_VERIFICATION.md (small, required for triage).
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
            # Do not reexec desktop.launcher — that opened a second desktop window on Windows.
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
                    "Dependency path: controller (base only — requirements.runtime.base.txt)",
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
                    "Dependency path: Browser Speech quick start (base only — requirements.runtime.base.txt)",
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
