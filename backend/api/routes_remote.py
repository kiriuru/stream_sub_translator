from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Request
import httpx

from backend.core.remote_diagnostics import build_remote_diagnostics
from backend.models import (
    RemoteHeartbeatRequest,
    RemoteHeartbeatResponse,
    RemotePairCreateRequest,
    RemotePairCreateResponse,
    RemotePairVerifyRequest,
    RemotePairVerifyResponse,
    RemoteStateResponse,
    RemoteWorkerHealthResponse,
    RemoteWorkerRuntimeActionResponse,
    RemoteWorkerSettingsSyncResponse,
    RemoteWorkerRuntimeStatusResponse,
)

router = APIRouter(prefix="/api/remote", tags=["remote"])


@router.get("/state", response_model=RemoteStateResponse)
async def remote_state(request: Request) -> RemoteStateResponse:
    settings = request.app.state.app_settings
    diagnostics = build_remote_diagnostics(
        request.app.state.config,
        app_host=settings.app_host,
        app_port=settings.app_port,
    )
    pairing = request.app.state.remote_session_manager.snapshot()
    return RemoteStateResponse(remote=diagnostics, pairing=pairing)


def _save_remote_pairing_state(
    request: Request,
    *,
    session_id: str,
    pair_code: str,
    enabled: bool = True,
    role: str = "controller",
) -> None:
    config_manager = request.app.state.config_manager
    current_config = request.app.state.config if isinstance(request.app.state.config, dict) else {}
    payload = deepcopy(current_config)
    remote = payload.get("remote", {})
    if not isinstance(remote, dict):
        remote = {}
    remote["enabled"] = bool(enabled)
    remote["role"] = str(role or "controller")
    remote["session_id"] = str(session_id or "").strip()
    remote["pair_code"] = str(pair_code or "").strip()
    payload["remote"] = remote
    saved_payload = config_manager.save(payload)
    request.app.state.config = saved_payload


@router.post("/pair/create", response_model=RemotePairCreateResponse)
async def create_remote_pair(request: Request, body: RemotePairCreateRequest) -> RemotePairCreateResponse:
    manager = request.app.state.remote_session_manager
    session_id, pair_code, expires_at_utc, pairing = manager.create_pairing(ttl_seconds=body.ttl_seconds)
    _save_remote_pairing_state(
        request,
        session_id=session_id,
        pair_code=pair_code,
        enabled=True,
        role="controller",
    )
    return RemotePairCreateResponse(
        session_id=session_id,
        pair_code=pair_code,
        expires_at_utc=expires_at_utc,
        pairing=pairing,
    )


@router.post("/pair/verify", response_model=RemotePairVerifyResponse)
async def verify_remote_pair(request: Request, body: RemotePairVerifyRequest) -> RemotePairVerifyResponse:
    manager = request.app.state.remote_session_manager
    accepted, reason = manager.verify_pairing(session_id=body.session_id, pair_code=body.pair_code)
    if not accepted:
        return RemotePairVerifyResponse(accepted=False, reason=reason, pairing=manager.snapshot())
    _, _, pairing = manager.heartbeat(session_id=body.session_id, role="worker")
    return RemotePairVerifyResponse(accepted=True, pairing=pairing)


@router.post("/heartbeat", response_model=RemoteHeartbeatResponse)
async def remote_heartbeat(request: Request, body: RemoteHeartbeatRequest) -> RemoteHeartbeatResponse:
    manager = request.app.state.remote_session_manager
    accepted, reason, pairing = manager.heartbeat(
        session_id=body.session_id,
        role=body.role,
    )
    return RemoteHeartbeatResponse(
        accepted=accepted,
        reason=reason,
        pairing=pairing,
    )


def _current_remote_config(request: Request) -> dict[str, Any]:
    payload = request.app.state.config if isinstance(request.app.state.config, dict) else {}
    remote = payload.get("remote", {})
    return remote if isinstance(remote, dict) else {}


def _configured_worker_url(request: Request) -> str | None:
    remote = _current_remote_config(request)
    controller = remote.get("controller", {})
    if not isinstance(controller, dict):
        return None
    worker_url = str(controller.get("worker_url", "") or "").strip()
    return worker_url or None


def _controller_connect_timeout_seconds(request: Request) -> float:
    remote = _current_remote_config(request)
    controller = remote.get("controller", {})
    if not isinstance(controller, dict):
        return 8.0
    try:
        timeout_ms = int(controller.get("connect_timeout_ms", 8000) or 8000)
    except (TypeError, ValueError):
        timeout_ms = 8000
    return max(1.0, min(120.0, float(timeout_ms) / 1000.0))


def _build_target_url(base_url: str, path: str) -> str:
    normalized_base = str(base_url or "").strip().rstrip("/")
    normalized_path = "/" + str(path or "").lstrip("/")
    return f"{normalized_base}{normalized_path}"


async def _proxy_worker_request(
    request: Request,
    *,
    method: str,
    path: str,
    json_payload: dict[str, Any] | None = None,
) -> tuple[str | None, dict[str, Any] | None, str | None]:
    worker_url = _configured_worker_url(request)
    if not worker_url:
        return None, None, "Worker URL is not configured in remote.controller.worker_url."
    target_url = _build_target_url(worker_url, path)
    timeout_seconds = _controller_connect_timeout_seconds(request)
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            if method.upper() == "GET":
                response = await client.get(target_url)
            elif method.upper() == "POST":
                response = await client.post(target_url, json=json_payload or {})
            else:
                return worker_url, None, f"Unsupported proxy method: {method}"
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                return worker_url, None, "Worker response is not a JSON object."
            return worker_url, body, None
    except Exception as exc:
        return worker_url, None, str(exc)


def _build_worker_sync_sections(request: Request) -> tuple[dict[str, Any], list[str]]:
    config = request.app.state.config if isinstance(request.app.state.config, dict) else {}
    sync_payload: dict[str, Any] = {}
    sections: list[str] = []

    translation = config.get("translation", {})
    if isinstance(translation, dict):
        sync_payload["translation"] = deepcopy(translation)
        sections.append("translation")

    subtitle_output = config.get("subtitle_output", {})
    if isinstance(subtitle_output, dict):
        sync_payload["subtitle_output"] = deepcopy(subtitle_output)
        sections.append("subtitle_output")

    source_lang = str(config.get("source_lang", "auto") or "").strip() or "auto"
    sync_payload["source_lang"] = source_lang
    sections.append("source_lang")

    # Worker must remain AI runtime only in remote mode.
    sync_payload["asr"] = {"mode": "local"}
    sections.append("asr.mode")
    return sync_payload, sections


def _merge_worker_settings_payload(
    worker_payload: dict[str, Any],
    sync_payload: dict[str, Any],
) -> dict[str, Any]:
    merged = deepcopy(worker_payload)

    translation = sync_payload.get("translation")
    if isinstance(translation, dict):
        merged["translation"] = deepcopy(translation)

    subtitle_output = sync_payload.get("subtitle_output")
    if isinstance(subtitle_output, dict):
        merged["subtitle_output"] = deepcopy(subtitle_output)

    if "source_lang" in sync_payload:
        merged["source_lang"] = str(sync_payload.get("source_lang", "auto") or "auto")

    current_asr = merged.get("asr", {})
    if not isinstance(current_asr, dict):
        current_asr = {}
    current_asr["mode"] = "local"
    merged["asr"] = current_asr
    return merged


@router.post("/worker/runtime/start", response_model=RemoteWorkerRuntimeActionResponse)
async def worker_runtime_start(request: Request) -> RemoteWorkerRuntimeActionResponse:
    worker_url, body, error = await _proxy_worker_request(
        request,
        method="POST",
        path="/api/runtime/start",
        json_payload={"device_id": None},
    )
    if error:
        return RemoteWorkerRuntimeActionResponse(
            ok=False,
            action="start",
            worker_url=worker_url,
            worker_runtime=None,
            error=error,
        )
    worker_runtime_payload = body.get("runtime", {}) if isinstance(body, dict) else {}
    return RemoteWorkerRuntimeActionResponse(
        ok=bool(body.get("ok", True)),
        action="start",
        worker_url=worker_url,
        worker_runtime=worker_runtime_payload if isinstance(worker_runtime_payload, dict) else None,
        error=None,
    )


@router.post("/worker/settings/sync", response_model=RemoteWorkerSettingsSyncResponse)
async def worker_settings_sync(request: Request) -> RemoteWorkerSettingsSyncResponse:
    sync_payload, sections = _build_worker_sync_sections(request)

    worker_url, worker_settings, load_error = await _proxy_worker_request(
        request,
        method="GET",
        path="/api/settings/load",
    )
    if load_error:
        return RemoteWorkerSettingsSyncResponse(
            ok=False,
            worker_url=worker_url,
            synced_sections=sections,
            error=load_error,
        )
    worker_payload = worker_settings.get("payload", {}) if isinstance(worker_settings, dict) else {}
    if not isinstance(worker_payload, dict):
        return RemoteWorkerSettingsSyncResponse(
            ok=False,
            worker_url=worker_url,
            synced_sections=sections,
            error="Worker settings payload is missing or invalid.",
        )

    merged_payload = _merge_worker_settings_payload(worker_payload, sync_payload)
    worker_url, worker_save_response, save_error = await _proxy_worker_request(
        request,
        method="POST",
        path="/api/settings/save",
        json_payload={"payload": merged_payload},
    )
    if save_error:
        return RemoteWorkerSettingsSyncResponse(
            ok=False,
            worker_url=worker_url,
            synced_sections=sections,
            error=save_error,
        )

    saved_payload = worker_save_response.get("payload", {}) if isinstance(worker_save_response, dict) else {}
    translation = saved_payload.get("translation", {}) if isinstance(saved_payload, dict) else {}
    target_languages = []
    if isinstance(translation, dict):
        raw_targets = translation.get("target_languages", [])
        if isinstance(raw_targets, list):
            target_languages = [str(item).strip().lower() for item in raw_targets if str(item).strip()]
    asr = saved_payload.get("asr", {}) if isinstance(saved_payload, dict) else {}
    asr_mode = str(asr.get("mode", "local") or "local") if isinstance(asr, dict) else "local"
    translation_enabled = bool(translation.get("enabled")) if isinstance(translation, dict) else None

    return RemoteWorkerSettingsSyncResponse(
        ok=True,
        worker_url=worker_url,
        synced_sections=sections,
        worker_translation_enabled=translation_enabled,
        worker_target_languages=target_languages,
        worker_asr_mode=asr_mode,
        error=None,
    )


@router.post("/worker/runtime/stop", response_model=RemoteWorkerRuntimeActionResponse)
async def worker_runtime_stop(request: Request) -> RemoteWorkerRuntimeActionResponse:
    worker_url, body, error = await _proxy_worker_request(
        request,
        method="POST",
        path="/api/runtime/stop",
        json_payload={},
    )
    if error:
        return RemoteWorkerRuntimeActionResponse(
            ok=False,
            action="stop",
            worker_url=worker_url,
            worker_runtime=None,
            error=error,
        )
    worker_runtime_payload = body.get("runtime", {}) if isinstance(body, dict) else {}
    return RemoteWorkerRuntimeActionResponse(
        ok=bool(body.get("ok", True)),
        action="stop",
        worker_url=worker_url,
        worker_runtime=worker_runtime_payload if isinstance(worker_runtime_payload, dict) else None,
        error=None,
    )


@router.get("/worker/runtime/status", response_model=RemoteWorkerRuntimeStatusResponse)
async def worker_runtime_status(request: Request) -> RemoteWorkerRuntimeStatusResponse:
    worker_url, body, error = await _proxy_worker_request(
        request,
        method="GET",
        path="/api/runtime/status",
    )
    if error:
        return RemoteWorkerRuntimeStatusResponse(
            ok=False,
            worker_url=worker_url,
            worker_runtime=None,
            error=error,
        )
    return RemoteWorkerRuntimeStatusResponse(
        ok=True,
        worker_url=worker_url,
        worker_runtime=body if isinstance(body, dict) else None,
        error=None,
    )


@router.get("/worker/health", response_model=RemoteWorkerHealthResponse)
async def worker_health(request: Request) -> RemoteWorkerHealthResponse:
    worker_url, body, error = await _proxy_worker_request(
        request,
        method="GET",
        path="/api/health",
    )
    if error:
        return RemoteWorkerHealthResponse(
            ok=False,
            worker_url=worker_url,
            health=None,
            error=error,
        )
    return RemoteWorkerHealthResponse(
        ok=True,
        worker_url=worker_url,
        health=body if isinstance(body, dict) else None,
        error=None,
    )
