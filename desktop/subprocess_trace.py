"""Structured subprocess lifecycle trace for the desktop launcher stack."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

_LOG_NAME = "subprocess-trace.jsonl"
_ENV_PREFIXES = ("SST_", "PYTHON", "PIP_", "HF_", "TORCH_", "CUDA_", "TMP", "TEMP")
_instance: SubprocessTraceLog | None = None
_lock = threading.RLock()


def _process_role(process: subprocess.Popen[Any]) -> str:
    role = getattr(process, "_sst_subprocess_role", None)
    return str(role or "").strip() or "unknown"


def attach_process_role(process: subprocess.Popen[Any], role: str) -> subprocess.Popen[Any]:
    setattr(process, "_sst_subprocess_role", str(role or "").strip() or "unknown")
    return process


def summarize_subprocess_args(args: list[str]) -> dict[str, Any]:
    if not args:
        return {"argv": [], "argv0": None, "kind": "empty"}
    argv0 = str(args[0])
    kind = Path(argv0).name.lower() if argv0 else "unknown"
    payload: dict[str, Any] = {
        "argv0": argv0,
        "argc": len(args),
        "kind": kind,
    }
    if len(args) > 1 and args[1] == "-c":
        payload["mode"] = "python_c"
        code = str(args[2]) if len(args) > 2 else ""
        payload["code_preview"] = code[:240] + ("..." if len(code) > 240 else "")
    elif len(args) > 1 and args[1].startswith("-"):
        payload["mode"] = "flagged"
        payload["argv_tail"] = args[1:8]
    else:
        payload["mode"] = "argv"
        payload["argv_tail"] = args[1:8]
    return payload


def summarize_subprocess_env(env: Mapping[str, str] | None) -> dict[str, str]:
    if not env:
        return {}
    selected: dict[str, str] = {}
    for key, value in env.items():
        upper = str(key).upper()
        if any(upper.startswith(prefix) for prefix in _ENV_PREFIXES):
            selected[str(key)] = str(value)
    return dict(sorted(selected.items()))


class SubprocessTraceLog:
    def __init__(self, logs_dir: Path, *, text_log: Callable[[str], None] | None = None) -> None:
        self._logs_dir = Path(logs_dir)
        self._text_log = text_log
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._sequence = 0
        self._monotonic_origin = time.perf_counter()
        self._active_children: dict[int, dict[str, Any]] = {}

    @classmethod
    def configure(cls, logs_dir: Path, *, text_log: Callable[[str], None] | None = None) -> SubprocessTraceLog:
        global _instance
        with _lock:
            if _instance is None:
                _instance = SubprocessTraceLog(logs_dir, text_log=text_log)
                _instance.reset()
            elif text_log is not None:
                _instance._text_log = text_log
            return _instance

    @classmethod
    def get(cls) -> SubprocessTraceLog | None:
        return _instance

    def reset(self) -> None:
        with _lock:
            self._active_children.clear()
        try:
            self._logs_dir.mkdir(parents=True, exist_ok=True)
            self.path().write_text("", encoding="utf-8")
        except OSError:
            return

    def path(self) -> Path:
        return self._logs_dir / _LOG_NAME

    def log(self, phase: str, event: str, **fields: Any) -> None:
        normalized_phase = str(phase or "").strip() or "subprocess"
        normalized_event = str(event or "").strip()
        if not normalized_event:
            return
        with _lock:
            self._sequence += 1
            record: dict[str, Any] = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "session_id": self._session_id,
                "sequence": self._sequence,
                "elapsed_ms": round((time.perf_counter() - self._monotonic_origin) * 1000.0, 2),
                "phase": normalized_phase,
                "event": normalized_event,
                "parent_process_id": os.getpid(),
                "thread": {
                    "id": threading.get_ident(),
                    "name": threading.current_thread().name,
                },
            }
            if fields:
                record["fields"] = {str(key): value for key, value in fields.items() if value is not None}
            self._append_record(record)
        self._emit_text(normalized_phase, normalized_event, fields)

    def _emit_text(self, phase: str, event: str, fields: Mapping[str, Any]) -> None:
        if self._text_log is None:
            return
        parts = [f"[subprocess] {phase}.{event}"]
        for key in ("role", "pid", "return_code", "action", "description", "active_child_count"):
            if key in fields and fields[key] is not None:
                parts.append(f"{key}={fields[key]}")
        self._text_log(" ".join(parts))

    def _append_record(self, record: Mapping[str, Any]) -> None:
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
            with self.path().open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
        except OSError:
            return

    def track_spawn(
        self,
        *,
        role: str,
        process: subprocess.Popen[Any],
        args: list[str],
        cwd: str | None,
        env: Mapping[str, str] | None,
        description: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        pid = int(process.pid or 0)
        fields: dict[str, Any] = {
            "role": role,
            "pid": pid or None,
            "description": description,
            "cwd": cwd,
            **summarize_subprocess_args(args),
            "env": summarize_subprocess_env(env),
        }
        if extra:
            fields.update(dict(extra))
        with _lock:
            if pid:
                self._active_children[pid] = {
                    "role": role,
                    "spawned_at_ms": round((time.perf_counter() - self._monotonic_origin) * 1000.0, 2),
                }
            fields["active_child_count"] = len(self._active_children)
        self.log("subprocess", "spawn", **fields)

    def track_exit(
        self,
        *,
        role: str,
        pid: int | None,
        return_code: int | None,
        duration_ms: float | None = None,
        description: str | None = None,
        process: subprocess.Popen[Any] | None = None,
    ) -> None:
        if process is not None and getattr(process, "_sst_exit_logged", False):
            return
        if process is not None:
            setattr(process, "_sst_exit_logged", True)
        resolved_pid = int(pid or 0)
        with _lock:
            if resolved_pid:
                self._active_children.pop(resolved_pid, None)
            active_child_count = len(self._active_children)
        self.log(
            "subprocess",
            "exit",
            role=role,
            pid=resolved_pid or None,
            return_code=return_code,
            duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            description=description,
            active_child_count=active_child_count,
        )

    def track_terminate(
        self,
        *,
        role: str,
        pid: int | None,
        action: str,
        return_code: int | None = None,
    ) -> None:
        resolved_pid = int(pid or 0)
        with _lock:
            if resolved_pid and action in {"kill", "exited"}:
                self._active_children.pop(resolved_pid, None)
            active_child_count = len(self._active_children)
        self.log(
            "subprocess",
            "terminate",
            role=role,
            pid=resolved_pid or None,
            action=action,
            return_code=return_code,
            active_child_count=active_child_count,
        )

    def track_registry(self, *, event: str, role: str, pid: int | None) -> None:
        with _lock:
            active_child_count = len(self._active_children)
        self.log(
            "subprocess",
            event,
            role=role,
            pid=pid,
            active_child_count=active_child_count,
        )


def configure_subprocess_trace(
    logs_dir: Path,
    *,
    text_log: Callable[[str], None] | None = None,
) -> SubprocessTraceLog:
    return SubprocessTraceLog.configure(logs_dir, text_log=text_log)


def subprocess_trace(phase: str, event: str, **fields: Any) -> None:
    logger = SubprocessTraceLog.get()
    if logger is None:
        return
    logger.log(phase, event, **fields)


def logged_popen(
    role: str,
    args: list[str],
    *,
    description: str | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    watch_exit: bool = True,
    extra: Mapping[str, Any] | None = None,
    **popen_kwargs: Any,
) -> subprocess.Popen[Any]:
    process = subprocess.Popen(args, cwd=str(cwd) if cwd is not None else None, env=env, **popen_kwargs)
    attach_process_role(process, role)
    logger = SubprocessTraceLog.get()
    if logger is not None:
        logger.track_spawn(
            role=role,
            process=process,
            args=args,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            description=description,
            extra=extra,
        )
    if watch_exit:
        watch_subprocess_exit(role, process, description=description)
    return process


def watch_subprocess_exit(
    role: str,
    process: subprocess.Popen[Any],
    *,
    description: str | None = None,
) -> None:
    spawned_at = time.perf_counter()

    def _waiter() -> None:
        return_code = process.wait()
        duration_ms = (time.perf_counter() - spawned_at) * 1000.0
        logger = SubprocessTraceLog.get()
        if logger is not None:
            logger.track_exit(
                role=role,
                pid=process.pid,
                return_code=return_code,
                duration_ms=duration_ms,
                description=description,
                process=process,
            )

    threading.Thread(
        target=_waiter,
        name=f"sst-subprocess-exit-{role}",
        daemon=True,
    ).start()


def log_subprocess_terminate(
    process: subprocess.Popen[Any],
    *,
    role: str | None = None,
    action: str,
    return_code: int | None = None,
) -> None:
    logger = SubprocessTraceLog.get()
    if logger is None:
        return
    logger.track_terminate(
        role=role or _process_role(process),
        pid=process.pid,
        action=action,
        return_code=return_code,
    )
