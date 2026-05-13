from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Mapping

_LEVEL_SHORT: dict[int, str] = {
    logging.DEBUG: "DBG",
    logging.INFO: "INF",
    logging.WARNING: "WRN",
    logging.ERROR: "ERR",
    logging.CRITICAL: "CRT",
}


def short_logger_component(logger_name: str) -> str:
    """Last segment of logger name, title-cased like Streamer.bot's 'Twitch Service'."""
    base = (logger_name or "root").strip()
    if not base:
        return "Root"
    tail = base.rsplit(".", 1)[-1]
    return tail.replace("_", " ").title()


def format_backend_log_line(record: logging.LogRecord) -> str:
    """Build `[YYYY-MM-DD HH:MM:SS.mmm LVL] Component :: message` (local time, ms)."""
    try:
        ct = datetime.fromtimestamp(record.created)
        ts = ct.strftime("%Y-%m-%d %H:%M:%S") + f".{int(record.msecs):03d}"
    except Exception:
        ts = "1970-01-01 00:00:00.000"
    lvl = _LEVEL_SHORT.get(record.levelno, (record.levelname or "???")[:3].upper())
    name = short_logger_component(record.name)
    msg = record.getMessage()
    line = f"[{ts} {lvl}] {name} :: {msg}"
    if record.exc_info:
        try:
            line = line + "\n" + logging.Formatter().formatException(record.exc_info)
        except Exception:
            pass
    elif record.exc_text:
        line = line + "\n" + str(record.exc_text)
    if record.stack_info:
        try:
            line = line + "\n" + logging.Formatter().formatStack(record.stack_info)
        except Exception:
            pass
    return line


def structured_event_level(event: str) -> str:
    ev = (event or "").strip().lower()
    if ev in (
        "browser_worker_status",
        "browser_rearm_scheduled",
        "translation_queue_depth_changed",
    ):
        return "VRB"
    if ev in ("browser_onerror", "browser_degraded"):
        return "WRN"
    if ev in (
        "translation_publish_accepted",
        "browser_external_final",
        "diagnostics_bundle_exported",
        "browser_worker_disconnected",
    ):
        return "INF"
    return "DBG"


def _format_value(key: str, val: Any, *, max_len: int = 200) -> str:
    if isinstance(val, (dict, list)):
        raw = json.dumps(val, ensure_ascii=False)
    else:
        raw = str(val)
    raw = raw.replace("\n", "\\n")
    if len(raw) > max_len:
        raw = raw[: max_len - 1] + "…"
    if re.search(r"[\s\"=]", raw) or raw == "":
        esc = raw.replace("\\", "\\\\").replace('"', '\\"')
        return f'{key}="{esc}"'
    return f"{key}={raw}"


def format_structured_runtime_line(record: Mapping[str, Any]) -> str:
    """
    One-line human-readable runtime event (Streamer.bot style), local timestamp.
    """
    ts_raw = str(record.get("timestamp_utc") or "").strip()
    try:
        dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        else:
            dt = dt.replace(tzinfo=timezone.utc).astimezone()
        ts = dt.strftime("%Y-%m-%d %H:%M:%S") + f".{dt.microsecond // 1000:03d}"
    except Exception:
        ts = ts_raw[:26] if ts_raw else "1970-01-01 00:00:00.000"

    event = str(record.get("event") or "").strip()
    channel = str(record.get("channel") or "").strip()
    source = str(record.get("source") or "").strip()
    component_key = source or channel or "runtime"
    component_display = component_key.replace("_", " ").title()
    lvl = structured_event_level(event)

    skip = {"event", "channel", "source", "timestamp_utc"}
    parts: list[str] = []
    for k in sorted(record.keys()):
        if k in skip:
            continue
        v = record[k]
        if v is None or v == "None":
            continue
        parts.append(_format_value(str(k), v))

    detail = " ".join(parts)
    if detail:
        return f"[{ts} {lvl}] {component_display} :: {event} {detail}"
    return f"[{ts} {lvl}] {component_display} :: {event}"
