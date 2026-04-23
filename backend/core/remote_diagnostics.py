from __future__ import annotations

from typing import Any

from backend.core.remote_mode import resolve_configured_remote_state, resolve_effective_remote_role
from backend.models import RemoteDiagnostics


def build_remote_diagnostics(config: dict[str, Any] | None, *, app_host: str, app_port: int) -> RemoteDiagnostics:
    payload = config if isinstance(config, dict) else {}
    remote = payload.get("remote", {})
    if not isinstance(remote, dict):
        remote = {}
    lan = remote.get("lan", {})
    if not isinstance(lan, dict):
        lan = {}
    controller = remote.get("controller", {})
    if not isinstance(controller, dict):
        controller = {}

    enabled, configured_role = resolve_configured_remote_state(payload)
    effective_role = resolve_effective_remote_role(payload)
    worker_url = str(controller.get("worker_url", "") or "").strip() or None
    session_id = str(remote.get("session_id", "") or "").strip() or None
    pair_code_set = bool(str(remote.get("pair_code", "") or "").strip())

    message: str
    if not enabled:
        message = "Remote mode is disabled."
    elif effective_role == "controller":
        message = "Remote mode is enabled in controller role."
    elif effective_role == "worker":
        message = "Remote mode is enabled in worker role."
    else:
        message = "Remote mode is configured."

    return RemoteDiagnostics(
        enabled=enabled,
        configured_role=configured_role,
        effective_role=effective_role,
        lan_bind_enabled=bool(lan.get("bind_enabled", False)),
        lan_bind_host=str(app_host or "127.0.0.1"),
        lan_bind_port=int(app_port or 8765),
        worker_url=worker_url,
        session_id=session_id,
        pair_code_set=pair_code_set,
        message=message,
    )

