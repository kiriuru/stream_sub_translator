from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.api_errors import ApiException

from backend.models import (
    ProfileDeleteResponse,
    ProfileListResponse,
    ProfilePayload,
    ProfileResponse,
    ProfileWriteResponse,
)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("", response_model=ProfileListResponse)
async def list_profiles(request: Request) -> ProfileListResponse:
    profiles = request.app.state.profile_manager.list_profiles()
    return ProfileListResponse(profiles=profiles)


@router.get("/{name}", response_model=ProfileResponse)
async def load_profile(name: str, request: Request) -> ProfileResponse:
    try:
        payload = request.app.state.profile_manager.load_profile(name)
    except FileNotFoundError as exc:
        raise ApiException(
            code="PROFILE_NOT_FOUND",
            message=str(exc),
            status_code=404,
            details={"profile": name},
            recommended_action="Choose an existing profile or create it first.",
        ) from exc
    except ValueError as exc:
        raise ApiException(
            code="PROFILE_INVALID",
            message=str(exc),
            status_code=400,
            details={"profile": name},
        ) from exc
    return ProfileResponse(name=name, payload=payload)


@router.post("/{name}", response_model=ProfileWriteResponse)
async def save_profile(name: str, body: ProfilePayload, request: Request) -> ProfileWriteResponse:
    try:
        path, saved_payload = request.app.state.profile_manager.save_profile(name, body.payload)
    except ValueError as exc:
        raise ApiException(
            code="PROFILE_SAVE_FAILED",
            message=str(exc),
            status_code=400,
            details={"profile": name},
        ) from exc
    return ProfileWriteResponse(name=name, saved_to=str(path), payload=saved_payload)


@router.delete("/{name}", response_model=ProfileDeleteResponse)
async def delete_profile(name: str, request: Request) -> ProfileDeleteResponse:
    try:
        deleted = request.app.state.profile_manager.delete_profile(name)
    except ValueError as exc:
        raise ApiException(
            code="PROFILE_DELETE_FAILED",
            message=str(exc),
            status_code=400,
            details={"profile": name},
        ) from exc
    return ProfileDeleteResponse(name=name, deleted=deleted)
