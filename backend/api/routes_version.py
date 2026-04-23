from __future__ import annotations

from fastapi import APIRouter, Request

from backend.models import VersionInfoResponse
from backend.versioning import build_version_info_payload

router = APIRouter(prefix="/api", tags=["version"])


@router.get("/version", response_model=VersionInfoResponse)
async def version_info(request: Request) -> VersionInfoResponse:
    payload = build_version_info_payload(request.app.state.config)
    return VersionInfoResponse(**payload)
