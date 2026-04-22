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
    config_manager = request.app.state.config_manager
    payload = config_manager.load()
    request.app.state.config = payload
    return SettingsLoadResponse(
        payload=payload,
        subtitle_style_presets=config_manager.subtitle_style_presets(payload),
        font_catalog=config_manager.font_catalog(),
        loaded_from=str(request.app.state.app_settings.config_path),
    )


@router.post("/save", response_model=SettingsSaveResponse)
async def save_settings(payload: SettingsSaveRequest, request: Request) -> SettingsSaveResponse:
    config_manager = request.app.state.config_manager
    saved_payload = config_manager.save(payload.payload)
    request.app.state.config = saved_payload
    live_applied = False
    runtime_orchestrator = getattr(request.app.state, "runtime_orchestrator", None)
    if runtime_orchestrator is not None:
        await runtime_orchestrator.apply_live_settings(saved_payload)
        live_applied = True
    return SettingsSaveResponse(
        saved_to=str(request.app.state.app_settings.config_path),
        payload=saved_payload,
        subtitle_style_presets=config_manager.subtitle_style_presets(saved_payload),
        font_catalog=config_manager.font_catalog(),
        live_applied=live_applied,
    )
