from __future__ import annotations

from fastapi import APIRouter, Request

from backend.models import ClientLogEventRequest, ClientLogEventResponse


router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.post("/client-event", response_model=ClientLogEventResponse)
async def log_client_event(payload: ClientLogEventRequest, request: Request) -> ClientLogEventResponse:
    session_logger = getattr(request.app.state, "session_logger", None)
    if session_logger is not None:
        result = session_logger.log(
            payload.channel,
            payload.message,
            source=payload.source,
            details=payload.details,
        )
        if isinstance(result, dict):
            return ClientLogEventResponse.model_validate(result)
    return ClientLogEventResponse(ok=True, logged=False, reason="logger_unavailable")
