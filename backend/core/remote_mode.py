from __future__ import annotations

import os
from typing import Any


REMOTE_ROLE_DISABLED = "disabled"
REMOTE_ROLE_CONTROLLER = "controller"
REMOTE_ROLE_WORKER = "worker"
REMOTE_ROLES = {
    REMOTE_ROLE_DISABLED,
    REMOTE_ROLE_CONTROLLER,
    REMOTE_ROLE_WORKER,
}


def normalize_remote_role(raw_value: Any, *, fallback: str = REMOTE_ROLE_DISABLED) -> str:
    role = str(raw_value or fallback).strip().lower()
    if role not in REMOTE_ROLES:
        return fallback
    return role


def resolve_configured_remote_state(config: dict[str, Any] | None) -> tuple[bool, str]:
    payload = config if isinstance(config, dict) else {}
    remote = payload.get("remote", {})
    if not isinstance(remote, dict):
        remote = {}
    enabled = bool(remote.get("enabled", False))
    role = normalize_remote_role(remote.get("role", REMOTE_ROLE_DISABLED))
    if not enabled:
        return False, REMOTE_ROLE_DISABLED
    if role == REMOTE_ROLE_DISABLED:
        role = REMOTE_ROLE_CONTROLLER
    return True, role


def resolve_effective_remote_role(config: dict[str, Any] | None) -> str:
    raw_env_role = os.environ.get("SST_REMOTE_ROLE")
    if raw_env_role is not None and str(raw_env_role).strip():
        return normalize_remote_role(raw_env_role, fallback=REMOTE_ROLE_DISABLED)
    _, configured_role = resolve_configured_remote_state(config)
    return configured_role


def is_lan_bind_enabled(config: dict[str, Any] | None) -> bool:
    payload = config if isinstance(config, dict) else {}
    remote = payload.get("remote", {})
    if not isinstance(remote, dict):
        return False
    lan = remote.get("lan", {})
    if not isinstance(lan, dict):
        return False
    return bool(lan.get("bind_enabled", False))
