from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser

from backend.config import settings
from backend.core.remote_mode import (
    REMOTE_ROLE_DISABLED,
    REMOTE_ROLES,
    normalize_remote_role,
)
import uvicorn

from backend.server_runtime import describe_port_owner, is_port_in_use, wait_for_health


def wait_and_open_browser(url: str, *, timeout_seconds: int = 180) -> None:
    health_url = f"{url.rstrip('/')}/api/health"
    try:
        wait_for_health(health_url, timeout_seconds=timeout_seconds, poll_interval_seconds=1.0)
    except Exception:
        return
    webbrowser.open(url)


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _port_in_use_for_bind_host(bind_host: str, port: int) -> bool:
    hosts_to_check: list[str] = [bind_host]
    if bind_host in {"0.0.0.0", "::"}:
        hosts_to_check.append("127.0.0.1")
    checked: set[str] = set()
    for candidate in hosts_to_check:
        if candidate in checked:
            continue
        checked.add(candidate)
        if ":" in candidate:
            continue
        try:
            if is_port_in_use(candidate, port):
                return True
        except OSError:
            continue
    return False


def main(
    *,
    default_remote_role: str = REMOTE_ROLE_DISABLED,
    default_allow_lan: bool = False,
) -> None:
    env_remote_role = normalize_remote_role(os.environ.get("SST_REMOTE_ROLE", default_remote_role))
    if env_remote_role not in REMOTE_ROLES:
        env_remote_role = REMOTE_ROLE_DISABLED
    env_allow_lan = _env_flag("SST_ALLOW_LAN", default=default_allow_lan)

    parser = argparse.ArgumentParser(description="Run the local FastAPI app.")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development.")
    parser.add_argument("--host", type=str, default=None, help="Override bind host.")
    parser.add_argument("--port", type=int, default=None, help="Override bind port.")
    parser.add_argument("--allow-lan", action="store_true", default=env_allow_lan, help="Bind to 0.0.0.0 when host is not specified.")
    parser.add_argument(
        "--remote-role",
        choices=sorted(REMOTE_ROLES),
        default=env_remote_role,
        help="Set runtime remote role for diagnostics and future remote workflows.",
    )
    args = parser.parse_args()

    bind_host = (str(args.host).strip() if args.host else "")
    if not bind_host:
        bind_host = "0.0.0.0" if args.allow_lan else settings.app_host
    bind_port = int(args.port) if args.port is not None else int(settings.app_port)
    remote_role = normalize_remote_role(args.remote_role)

    settings.app_host = bind_host
    settings.app_port = bind_port
    os.environ["SST_REMOTE_ROLE"] = remote_role

    if _port_in_use_for_bind_host(bind_host, bind_port):
        owner = describe_port_owner(bind_port)
        print(
            f"[startup] Cannot start a new server because {bind_host}:{bind_port} is already in use.",
            file=sys.stderr,
        )
        if owner:
            print(f"[startup] {owner}", file=sys.stderr)
        print(
            "[startup] Close the previous app instance or free the port, then run start.bat again.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"[startup] Runtime role: {remote_role}")
    print(f"[startup] Bind target: {bind_host}:{bind_port}")
    if bind_host in {"0.0.0.0", "::"}:
        print("[startup] LAN bind is enabled explicitly.")

    if args.open_browser:
        print("[startup] Waiting for local health check before opening the browser...")
        threading.Thread(
            target=wait_and_open_browser,
            args=(f"{settings.local_base_url}/",),
            daemon=True,
        ).start()

    uvicorn.run(
        "backend.app:app",
        host=bind_host,
        port=bind_port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
