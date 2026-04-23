from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from backend.models import ExportFileInfo, ExportsListResponse

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("", response_model=ExportsListResponse)
async def list_exports(request: Request) -> ExportsListResponse:
    export_dir = request.app.state.app_settings.data_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    items = sorted(
        (p for p in export_dir.glob("*") if p.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    files = [
        ExportFileInfo(
            name=path.name,
            size_bytes=path.stat().st_size,
            modified_utc=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        )
        for path in items
    ]
    return ExportsListResponse(
        exports=[item.name for item in files],
        files=files,
    )
