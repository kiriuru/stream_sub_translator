from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

from backend.config import settings
import uvicorn

from backend.server_runtime import describe_port_owner, is_port_in_use, wait_for_health


def wait_and_open_browser(url: str, *, timeout_seconds: int = 180) -> None:
    health_url = f"{url.rstrip('/')}/api/health"
    try:
        wait_for_health(health_url, timeout_seconds=timeout_seconds, poll_interval_seconds=1.0)
    except Exception:
        return
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local FastAPI app.")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development.")
    args = parser.parse_args()

    if is_port_in_use(settings.app_host, settings.app_port):
        owner = describe_port_owner(settings.app_port)
        print(
            f"[startup] Cannot start a new server because {settings.app_host}:{settings.app_port} is already in use.",
            file=sys.stderr,
        )
        if owner:
            print(f"[startup] {owner}", file=sys.stderr)
        print(
            "[startup] Close the previous app instance or free the port, then run start.bat again.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if args.open_browser:
        print("[startup] Waiting for local health check before opening the browser...")
        threading.Thread(
            target=wait_and_open_browser,
            args=(f"{settings.local_base_url}/",),
            daemon=True,
        ).start()

    uvicorn.run(
        "backend.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
