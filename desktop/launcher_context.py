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
from desktop.splash_i18n_cjk import SPLASH_I18N_JA, SPLASH_I18N_KO, SPLASH_I18N_ZH
from desktop.splash_screen import build_splash_html
from desktop.ui_locale import SUPPORTED_UI_LANGUAGES, normalize_ui_language

# Shared launcher constants, config helpers, and HTTP wait utilities.


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
    "ja": SPLASH_I18N_JA,
    "ko": SPLASH_I18N_KO,
    "zh": SPLASH_I18N_ZH,
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
    return normalize_ui_language(value)


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


