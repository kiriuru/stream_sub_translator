from __future__ import annotations

from fastapi import APIRouter, Body, Request

from backend.models import ObsUrlResponse, RuntimeActionResponse, RuntimeStartRequest, RuntimeState

router = APIRouter(prefix="/api", tags=["runtime"])


@router.post("/runtime/start", response_model=RuntimeActionResponse)
async def runtime_start(request: Request, body: RuntimeStartRequest | None = Body(default=None)) -> RuntimeActionResponse:
    service = request.app.state.runtime_service
    return await service.start(body)


@router.post("/runtime/stop", response_model=RuntimeActionResponse)
async def runtime_stop(request: Request) -> RuntimeActionResponse:
    service = request.app.state.runtime_service
    return await service.stop()


@router.get("/runtime/status", response_model=RuntimeState)
async def runtime_status(request: Request) -> RuntimeState:
    service = request.app.state.runtime_service
    return service.status()


@router.get("/obs/url", response_model=ObsUrlResponse)
async def obs_url(request: Request) -> ObsUrlResponse:
    service = request.app.state.runtime_service
    return service.obs_url()
