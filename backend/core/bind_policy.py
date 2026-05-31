from __future__ import annotations

import os

from backend.config import settings


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_bind_host(
    *,
    host: str | None,
    allow_lan: bool,
    default_host: str | None = None,
) -> str:
    explicit = (str(host).strip() if host else "")
    if explicit:
        return explicit
    if allow_lan:
        return "0.0.0.0"
    fallback = (default_host or settings.app_host or "127.0.0.1").strip()
    return fallback or "127.0.0.1"
