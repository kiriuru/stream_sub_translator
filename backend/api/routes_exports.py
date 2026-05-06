from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from backend.models import ExportsListResponse

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("", response_model=ExportsListResponse)
async def list_exports(request: Request) -> ExportsListResponse:
    service = request.app.state.export_service
    return service.list_exports()


@router.get("/diagnostics")
async def export_diagnostics(request: Request) -> FileResponse:
    service = request.app.state.export_service
    bundle_path = service.export_diagnostics_bundle()
    return FileResponse(
        bundle_path,
        media_type="application/zip",
        filename=bundle_path.name,
    )
