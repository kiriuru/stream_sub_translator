from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from desktop.bootstrap_payload import (
    BOOTSTRAP_INSTALL_MARKER,
    BOOTSTRAP_LOG_FILE,
    BOOTSTRAP_LOGS_DIR,
    BOOTSTRAP_RUNTIME_DIR,
    BOOTSTRAP_RUNTIME_HIDDEN_EXE,
    BOOTSTRAP_USER_DATA_DIR,
    PayloadManifest,
    apply_windows_hidden_attribute,
    ensure_writable_directory,
    is_remote_version_newer,
    install_or_repair_runtime,
    read_manifest,
    verify_runtime_files,
)


APP_NAME = "Stream Subtitle Translator"
GITHUB_RELEASES_REPO = "kiriuru/stream_sub_translator"
GITHUB_RELEASE_CHANNEL = "stable"


def _show_error_dialog(title: str, message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        print(f"{title}: {message}")


@dataclass(frozen=True)
class BootstrapPaths:
    exe_path: Path
    exe_dir: Path
    payload_zip: Path
    payload_manifest: Path
    runtime_exe: Path
    runtime_dir: Path
    user_data_dir: Path
    logs_dir: Path
    log_path: Path


class BootstrapUi:
    def __init__(self, title: str) -> None:
        self._title = title
        self._window = None
        self._status_var = None
        self._detail_var = None
        self._action_lock = threading.Lock()
        self._pending_action: str | None = None
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def _run(self) -> None:
        try:
            import tkinter as tk
            from tkinter import ttk

            window = tk.Tk()
            window.title(self._title)
            window.geometry("520x180")
            window.resizable(False, False)
            window.configure(bg="#09111b")
            window.attributes("-topmost", True)
            status_var = tk.StringVar(value="Preparing bootstrap runtime...")
            detail_var = tk.StringVar(value="Checking embedded payload...")
            frame = ttk.Frame(window, padding=20)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text=self._title, font=("Segoe UI", 20, "bold")).pack(anchor="w")
            ttk.Label(frame, textvariable=status_var, wraplength=460).pack(anchor="w", pady=(16, 6))
            progress = ttk.Progressbar(frame, mode="indeterminate", length=420)
            progress.pack(anchor="w", pady=(0, 12))
            progress.start(10)
            ttk.Label(frame, textvariable=detail_var, wraplength=460).pack(anchor="w")
            actions = ttk.Frame(frame)
            actions.pack(fill="x", pady=(16, 0))
            ttk.Button(actions, text="Repair Runtime", command=lambda: self._queue_action("repair")).pack(side="left")
            ttk.Button(actions, text="Reset Runtime", command=lambda: self._queue_action("reset")).pack(side="left", padx=(10, 0))
            ttk.Button(actions, text="Open Log", command=lambda: self._queue_action("show_log")).pack(side="right")
            window.protocol("WM_DELETE_WINDOW", lambda: None)
            self._window = window
            self._status_var = status_var
            self._detail_var = detail_var
            self._ready.set()
            window.mainloop()
        except Exception:
            self._ready.set()

    def _queue_action(self, action: str) -> None:
        with self._action_lock:
            self._pending_action = action

    def consume_action(self) -> str | None:
        with self._action_lock:
            action = self._pending_action
            self._pending_action = None
            return action

    def update(self, status: str, detail: str | None = None) -> None:
        if self._closed.is_set():
            return
        window = self._window
        if window is None or self._status_var is None:
            return

        def apply() -> None:
            self._status_var.set(status)
            if detail is not None and self._detail_var is not None:
                self._detail_var.set(detail)
            window.update_idletasks()

        try:
            window.after(0, apply)
        except Exception:
            return

    def close(self) -> None:
        self._closed.set()
        window = self._window
        if window is None:
            return
        try:
            window.after(0, window.destroy)
        except Exception:
            return

    def prompt_update_available(self, *, current_version: str, latest_version: str, release_url: str) -> str:
        """
        Blocking prompt on the UI thread.

        Returns: "continue" or "download"
        """
        window = self._window
        if window is None:
            return "continue"

        choice_event = threading.Event()
        choice_holder: dict[str, str] = {"choice": "continue"}

        def show_dialog() -> None:
            try:
                import tkinter as tk
                from tkinter import ttk

                dialog = tk.Toplevel(window)
                dialog.title("Update available")
                dialog.geometry("520x220")
                dialog.resizable(False, False)
                dialog.configure(bg="#09111b")
                dialog.attributes("-topmost", True)
                dialog.transient(window)
                dialog.grab_set()

                frame = ttk.Frame(dialog, padding=20)
                frame.pack(fill="both", expand=True)

                ttk.Label(frame, text="A new version is available", font=("Segoe UI", 16, "bold")).pack(anchor="w")
                ttk.Label(
                    frame,
                    text=f"Current: {current_version}\nLatest: {latest_version}",
                    wraplength=460,
                    justify="left",
                ).pack(anchor="w", pady=(14, 6))
                ttk.Label(
                    frame,
                    text="You can continue launching now, or open the download page for the latest release.",
                    wraplength=460,
                    justify="left",
                ).pack(anchor="w")

                actions = ttk.Frame(frame)
                actions.pack(fill="x", pady=(18, 0))

                def pick(value: str) -> None:
                    choice_holder["choice"] = value
                    try:
                        dialog.grab_release()
                    except Exception:
                        pass
                    dialog.destroy()
                    choice_event.set()

                ttk.Button(actions, text="Continue", command=lambda: pick("continue")).pack(side="left")
                ttk.Button(actions, text="Download", command=lambda: pick("download")).pack(side="left", padx=(10, 0))
                ttk.Button(actions, text="Copy link", command=lambda: window.clipboard_append(release_url)).pack(
                    side="right"
                )

                dialog.protocol("WM_DELETE_WINDOW", lambda: None)
            except Exception:
                choice_event.set()

        try:
            window.after(0, show_dialog)
        except Exception:
            return "continue"

        choice_event.wait(timeout=120)
        return choice_holder.get("choice", "continue")


class BootstrapLauncher:
    def __init__(self) -> None:
        exe_path = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
        exe_dir = exe_path.parent
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        logs_dir = exe_dir / BOOTSTRAP_LOGS_DIR
        self._paths = BootstrapPaths(
            exe_path=exe_path,
            exe_dir=exe_dir,
            payload_zip=bundle_root / "payload.zip",
            payload_manifest=bundle_root / "payload.manifest.json",
            runtime_exe=exe_dir / BOOTSTRAP_RUNTIME_HIDDEN_EXE,
            runtime_dir=exe_dir / BOOTSTRAP_RUNTIME_DIR,
            user_data_dir=exe_dir / BOOTSTRAP_USER_DATA_DIR,
            logs_dir=logs_dir,
            log_path=logs_dir / BOOTSTRAP_LOG_FILE,
        )
        self._migrate_legacy_logs_dir()
        self._ui = BootstrapUi(APP_NAME)

    def _migrate_legacy_logs_dir(self) -> None:
        legacy_logs_dir = self._paths.exe_dir / "logs"
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

    def _log(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        self._paths.logs_dir.mkdir(parents=True, exist_ok=True)
        with self._paths.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")

    def _status(self, status: str, detail: str | None = None) -> None:
        self._log(f"status: {status}" + (f" | {detail}" if detail else ""))
        self._ui.update(status, detail)

    def _load_manifest(self) -> PayloadManifest:
        if not self._paths.payload_manifest.exists():
            raise RuntimeError(f"Missing embedded payload manifest: {self._paths.payload_manifest}")
        if not self._paths.payload_zip.exists():
            raise RuntimeError(f"Missing embedded payload archive: {self._paths.payload_zip}")
        return read_manifest(self._paths.payload_manifest)

    def _fetch_latest_release(self) -> tuple[str | None, str | None]:
        """
        Returns (latest_version, html_url) or (None, None) on failure.
        """
        api_url = f"https://api.github.com/repos/{GITHUB_RELEASES_REPO}/releases?per_page=12"
        req = Request(
            api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"{APP_NAME} bootstrap",
            },
            method="GET",
        )
        try:
            with urlopen(req, timeout=4) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except (OSError, URLError):
            return None, None
        try:
            payload = json.loads(raw)
        except Exception:
            return None, None
        if not isinstance(payload, list):
            return None, None

        best_version: str | None = None
        best_url: str | None = None
        for item in payload:
            if not isinstance(item, dict):
                continue
            if bool(item.get("draft", False)):
                continue
            is_prerelease = bool(item.get("prerelease", False))
            if GITHUB_RELEASE_CHANNEL == "stable" and is_prerelease:
                continue
            tag = str(item.get("tag_name", "") or "").strip()
            if not tag:
                continue
            version = tag.lstrip("v").strip()
            if not version:
                continue
            if best_version is None or is_remote_version_newer(best_version, version):
                best_version = version
                best_url = str(item.get("html_url", "") or "").strip() or None
        return best_version, best_url

    def _maybe_prompt_update(self, manifest: PayloadManifest) -> None:
        """
        Silent by default: prompts only when an update is available.
        """
        # This is a bootstrap launcher for a major desktop revamp: only show update prompts
        # when the remote version is newer than the currently embedded runtime version.
        current = str(manifest.app_version or "").strip()
        if not current:
            return
        self._status("Checking for updates...", f"GitHub Releases: {GITHUB_RELEASES_REPO}")
        latest, url = self._fetch_latest_release()
        if not latest or not is_remote_version_newer(current, latest):
            return
        release_url = url or f"https://github.com/{GITHUB_RELEASES_REPO}/releases/tag/v{latest}"
        self._log(f"update available: current={current} latest={latest} url={release_url}")
        choice = self._ui.prompt_update_available(
            current_version=current,
            latest_version=latest,
            release_url=release_url,
        )
        if choice == "download":
            try:
                os.startfile(release_url)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _ensure_portable_layout(self) -> None:
        self._status("Checking portable folder write access...", str(self._paths.exe_dir))
        ensure_writable_directory(self._paths.exe_dir)
        ensure_writable_directory(self._paths.user_data_dir)
        ensure_writable_directory(self._paths.logs_dir)

    def _open_log_file(self) -> None:
        self._paths.logs_dir.mkdir(parents=True, exist_ok=True)
        self._paths.log_path.touch(exist_ok=True)
        os.startfile(str(self._paths.log_path))  # type: ignore[attr-defined]

    def _poll_ui_actions(self, args: argparse.Namespace) -> None:
        action = self._ui.consume_action()
        if action is None:
            return
        if action == "repair":
            args.repair = True
            self._log("ui action selected: repair runtime")
            self._status("Repair Runtime selected.", "Managed runtime verification will be forced.")
            return
        if action == "reset":
            args.reset_runtime = True
            self._log("ui action selected: reset runtime")
            self._status("Reset Runtime selected.", "Managed runtime will be fully reinstalled.")
            return
        if action == "show_log":
            try:
                self._open_log_file()
                self._log("ui action selected: open log")
            except Exception as exc:
                self._log(f"open-log failed: {exc}")

    def _verify_runtime(self, manifest: PayloadManifest) -> tuple[bool, list[str]]:
        self._status("Verifying managed runtime files...", f"{manifest.app_version} / {manifest.release_track}")
        return verify_runtime_files(self._paths.exe_dir, manifest)

    def _install_or_repair(self, manifest: PayloadManifest) -> None:
        self._status("Repairing desktop runtime files...", "Installing embedded managed files next to the launcher.")
        verified, mismatches = install_or_repair_runtime(self._paths.exe_dir, manifest, self._paths.payload_zip, log=self._log)
        apply_windows_hidden_attribute(self._paths.runtime_exe)
        if not verified:
            raise RuntimeError(f"Managed runtime repair failed: {', '.join(mismatches[:8])}")

    def _launch_runtime(self, *extra_args: str) -> None:
        runtime_exe = self._paths.runtime_exe
        if not runtime_exe.exists():
            raise RuntimeError(f"Runtime executable is missing after install: {runtime_exe}")
        self._status("Launching desktop runtime...", runtime_exe.name)
        self._log(f"launching runtime exe: {runtime_exe}")
        subprocess.Popen(
            [str(runtime_exe), *extra_args],
            cwd=str(self._paths.exe_dir),
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            self._log(f"bootstrap start: exe={self._paths.exe_path}")
            time.sleep(0.6)
            self._poll_ui_actions(args)
            manifest = self._load_manifest()
            self._ensure_portable_layout()
            if not args.no_start:
                # If up-to-date, this stays silent and proceeds.
                self._maybe_prompt_update(manifest)
            self._poll_ui_actions(args)
            verified, mismatches = self._verify_runtime(manifest)
            self._poll_ui_actions(args)
            if args.reset_runtime:
                verified = False
                mismatches = ["forced-reset"]
            if args.repair or not verified:
                self._log("managed runtime install/repair required")
                if mismatches:
                    self._log("runtime mismatches: " + "; ".join(mismatches[:20]))
                self._install_or_repair(manifest)
                verified, mismatches = self._verify_runtime(manifest)
                if not verified:
                    raise RuntimeError(f"Managed runtime verification still fails after repair: {', '.join(mismatches[:8])}")
            if args.no_start:
                self._status("Managed runtime is ready.", "No-start mode requested.")
                time.sleep(1.0)
                return 0
            self._launch_runtime(*args.runtime_args)
            time.sleep(0.6)
            return 0
        except Exception as exc:
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            self._log("bootstrap failed: " + detail)
            _show_error_dialog(
                f"{APP_NAME} Bootstrap Error",
                f"{detail}\n\nSee log:\n{self._paths.log_path}",
            )
            return 1
        finally:
            self._ui.close()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap launcher for Stream Subtitle Translator.")
    parser.add_argument("--repair", action="store_true", help="Force runtime verification and repair before launch.")
    parser.add_argument("--reset-runtime", action="store_true", help="Force full managed runtime reinstall before launch.")
    parser.add_argument("--no-start", action="store_true", help="Verify and repair runtime only; do not launch the managed runtime.")
    parser.add_argument("--show-log", action="store_true", help="Open the bootstrap launcher log and exit.")
    parser.add_argument("runtime_args", nargs="*", help="Arguments forwarded to the managed runtime executable.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    launcher = BootstrapLauncher()
    if args.show_log:
        try:
            launcher._open_log_file()
            launcher._ui.close()
            return 0
        except Exception as exc:
            launcher._log(f"show-log failed: {exc}")
    return launcher.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
