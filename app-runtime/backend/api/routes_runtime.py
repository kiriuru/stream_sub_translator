from __future__ import annotations

from fastapi import APIRouter, Body, Request

from backend.models import ObsUrlResponse, RuntimeActionResponse, RuntimeStartRequest, RuntimeState

router = APIRouter(prefix="/api", tags=["runtime"])


@router.post("/runtime/start", response_model=RuntimeActionResponse)
async def runtime_start(request: Request, body: RuntimeStartRequest | None = Body(default=None)) -> RuntimeActionResponse:
    body = body or RuntimeStartRequest()
    devices = request.app.state.audio_device_manager.list_input_devices()
    state = await request.app.state.runtime_orchestrator.start(
        has_audio_inputs=bool(devices),
        device_id=body.device_id,
    )
    return RuntimeActionResponse(action="start", runtime=state)


@router.post("/runtime/stop", response_model=RuntimeActionResponse)
async def runtime_stop(request: Request) -> RuntimeActionResponse:
    state = await request.app.state.runtime_orchestrator.stop()
    return RuntimeActionResponse(action="stop", runtime=state)


@router.get("/runtime/status", response_model=RuntimeState)
async def runtime_status(request: Request) -> RuntimeState:
    return request.app.state.runtime_orchestrator.status()


@router.get("/obs/url", response_model=ObsUrlResponse)
async def obs_url(request: Request) -> ObsUrlResponse:
    settings = request.app.state.app_settings
    return ObsUrlResponse(overlay_url=f"{settings.local_base_url}/overlay")
