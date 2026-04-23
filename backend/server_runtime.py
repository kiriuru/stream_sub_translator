from __future__ import annotations

import asyncio
import importlib
import socket
import threading
import time
from typing import Any, Callable

import httpx
import uvicorn


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def describe_port_owner(port: int) -> str | None:
    try:
        psutil = importlib.import_module("psutil")
    except Exception:
        return None

    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                pid = conn.pid
                if pid is None:
                    return f"PID unknown is already listening on port {port}."
                try:
                    proc = psutil.Process(pid)
                    return f"PID {pid} ({proc.name()}) is already listening on port {port}."
                except Exception:
                    return f"PID {pid} is already listening on port {port}."
    except Exception:
        return None
    return None


def wait_for_health(
    health_url: str,
    *,
    timeout_seconds: int = 180,
    poll_interval_seconds: float = 0.5,
    abort_if: Callable[[], str | None] | None = None,
    on_retry: Callable[[int, str | None], None] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        if abort_if is not None:
            abort_reason = abort_if()
            if abort_reason:
                raise RuntimeError(abort_reason)
        try:
            response = httpx.get(health_url, timeout=5.0)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = str(exc)
            if on_retry is not None:
                on_retry(attempt, last_error)
            time.sleep(poll_interval_seconds)
    raise TimeoutError(f"Health check did not become ready within {timeout_seconds}s. Last error: {last_error or 'unknown'}")


class LocalServerThread:
    def __init__(
        self,
        *,
        app: Any,
        host: str,
        port: int,
        log_level: str = "info",
    ) -> None:
        self._config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=log_level,
            log_config=None,
            access_log=False,
            reload=False,
        )
        self._server = uvicorn.Server(self._config)
        self._thread = threading.Thread(
            target=self._serve,
            name="stream-sub-translator-server",
            daemon=True,
        )
        self.startup_error: Exception | None = None
        self._started = False

    def _serve(self) -> None:
        try:
            asyncio.run(self._server.serve())
        except Exception as exc:
            self.startup_error = exc

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread.start()

    def stop(self, *, timeout_seconds: float = 15.0) -> None:
        if not self._started:
            return
        self._server.should_exit = True
        self._thread.join(timeout_seconds)
        if self._thread.is_alive():
            self._server.force_exit = True
            self._thread.join(5.0)

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()
