"""Pywebview window navigation, resize, and splash DOM updates."""
from __future__ import annotations

import json
import threading
from typing import Any

from backend.core.ui_trace_log import ui_trace

from desktop.launcher_context import (
    DASHBOARD_WINDOW_SIZES,
    UI_LAYOUT_STANDARD,
    _load_ui_language,
    _load_ui_layout,
    _resize_pywebview_window,
    _splash_t,
)


class LauncherWindowMixin:
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
