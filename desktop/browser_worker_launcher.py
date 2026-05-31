"""Browser Speech worker window launch (Chrome, isolated profile)."""
from __future__ import annotations

import os
import shutil
import subprocess
import winreg
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import webbrowser

from desktop.launcher_context import (
    APP_NAME,
    _BROWSER_WORKER_EXPERIMENTAL_PATHS,
    _BROWSER_WORKER_PATHS,
    _classic_browser_worker_path_for_preference,
    _filesystem_relative_candidates_for_exes,
    _load_worker_launch_browser_preference,
    _show_error_dialog,
    ordered_browser_executable_names,
)
from desktop.subprocess_trace import logged_popen


class BrowserWorkerLauncherMixin:
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

