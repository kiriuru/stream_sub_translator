from __future__ import annotations

from fastapi import APIRouter, Request

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
    service = request.app.state.diagnostics_service
    return service.remote_state()


@router.post("/pair/create", response_model=RemotePairCreateResponse)
async def create_remote_pair(request: Request, body: RemotePairCreateRequest) -> RemotePairCreateResponse:
    manager = request.app.state.remote_session_manager
    session_id, pair_code, expires_at_utc, pairing = manager.create_pairing(ttl_seconds=body.ttl_seconds)
    request.app.state.settings_service.save_remote_pairing_state(
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


@router.post("/worker/runtime/start", response_model=RemoteWorkerRuntimeActionResponse)
async def worker_runtime_start(request: Request) -> RemoteWorkerRuntimeActionResponse:
    service = request.app.state.runtime_service
    return await service.worker_runtime_start()


@router.post("/worker/settings/sync", response_model=RemoteWorkerSettingsSyncResponse)
async def worker_settings_sync(request: Request) -> RemoteWorkerSettingsSyncResponse:
    service = request.app.state.settings_service
    return await service.worker_settings_sync()


@router.post("/worker/runtime/stop", response_model=RemoteWorkerRuntimeActionResponse)
async def worker_runtime_stop(request: Request) -> RemoteWorkerRuntimeActionResponse:
    service = request.app.state.runtime_service
    return await service.worker_runtime_stop()


@router.get("/worker/runtime/status", response_model=RemoteWorkerRuntimeStatusResponse)
async def worker_runtime_status(request: Request) -> RemoteWorkerRuntimeStatusResponse:
    service = request.app.state.runtime_service
    return await service.worker_runtime_status()


@router.get("/worker/health", response_model=RemoteWorkerHealthResponse)
async def worker_health(request: Request) -> RemoteWorkerHealthResponse:
    service = request.app.state.runtime_service
    return await service.worker_health()
