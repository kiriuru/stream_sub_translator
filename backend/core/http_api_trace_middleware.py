"""FastAPI middleware: structured request/response lines in api-trace.jsonl."""

from __future__ import annotations

import time
from typing import Callable

from starlette.requests import Request
from starlette.responses import Response

from backend.core.api_trace_log import api_trace

_ALWAYS_LOG_PREFIXES = ("/api/", "/ws/")
_ALWAYS_LOG_EXACT = {
    "/",
    "/overlay",
    "/google-asr",
    "/google-asr-experimental",
    "/google-asr-edge",
    "/google-asr-experimental-edge",
    "/remote/controller-bridge",
    "/remote/worker-bridge",
    "/project-fonts.css",
    "/favicon.ico",
}


def _should_log_http_path(path: str) -> bool:
    normalized = str(path or "/").split("?", 1)[0] or "/"
    if normalized in _ALWAYS_LOG_EXACT:
        return True
    if any(normalized.startswith(prefix) for prefix in _ALWAYS_LOG_PREFIXES):
        return True
    return False


async def http_api_trace_middleware(request: Request, call_next: Callable) -> Response:
    path = request.url.path or "/"
    should_log = _should_log_http_path(path)
    started = time.perf_counter()
    if should_log:
        api_trace(
            "http",
            "request_begin",
            method=request.method,
            path=path,
            query=str(request.url.query or "") or None,
            client_host=request.client.host if request.client else None,
        )
    try:
        response = await call_next(request)
    except Exception as exc:
        if should_log:
            api_trace(
                "http",
                "request_error",
                method=request.method,
                path=path,
                elapsed_ms=round((time.perf_counter() - started) * 1000.0, 2),
                error_kind=type(exc).__name__,
                error=str(exc)[:500],
            )
        raise
    if should_log:
        api_trace(
            "http",
            "request_complete",
            method=request.method,
            path=path,
            status_code=int(response.status_code),
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 2),
        )
    elif int(response.status_code) >= 400:
        api_trace(
            "http",
            "static_error",
            method=request.method,
            path=path,
            status_code=int(response.status_code),
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 2),
        )
    return response
