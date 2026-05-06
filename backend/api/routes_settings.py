from __future__ import annotations

from fastapi import APIRouter, Request

from backend.models import (
    SettingsLoadResponse,
    SettingsSaveRequest,
    SettingsSaveResponse,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/load", response_model=SettingsLoadResponse)
async def load_settings(request: Request) -> SettingsLoadResponse:
    service = request.app.state.settings_service
    return service.load()


@router.post("/save", response_model=SettingsSaveResponse)
async def save_settings(payload: SettingsSaveRequest, request: Request) -> SettingsSaveResponse:
    service = request.app.state.settings_service
    return await service.save(payload)
