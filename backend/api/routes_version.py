from __future__ import annotations

from fastapi import APIRouter, Request

from backend.models import VersionInfoResponse
router = APIRouter(prefix="/api", tags=["version"])


@router.get("/version", response_model=VersionInfoResponse)
async def version_info(request: Request) -> VersionInfoResponse:
    payload = request.app.state.diagnostics_service.version_info()
    return VersionInfoResponse(**payload)
