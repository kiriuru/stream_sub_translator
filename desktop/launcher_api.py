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

from desktop.launcher_context import (
    APP_HOST,
    APP_PORT,
    DESKTOP_PROFILE_LOCK_BROWSER_SPEECH,
    LAUNCH_OPTION_BROWSER,
    LAUNCH_OPTION_CPU,
    LAUNCH_OPTION_NVIDIA,
    LAUNCH_OPTION_REMOTE_CONTROLLER,
    LAUNCH_OPTION_REMOTE_WORKER,
    SPLASH_WINDOW_DEFAULT,
    STARTUP_MODE_BROWSER,
    STARTUP_MODE_LOCAL,
    LaunchContext,
    _classic_browser_worker_path_for_preference,
    _load_ui_language,
    _load_worker_launch_browser_preference,
    _normalize_ui_language,
    _resize_pywebview_window,
    _save_ui_language,
)

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


