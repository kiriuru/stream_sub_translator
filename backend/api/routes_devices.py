from __future__ import annotations

from fastapi import APIRouter, Request

from backend.models import AudioInputsResponse

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("/audio-inputs", response_model=AudioInputsResponse)
async def audio_inputs(request: Request) -> AudioInputsResponse:
    service = request.app.state.runtime_service
    return service.audio_inputs()
