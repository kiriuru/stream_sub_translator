from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.ui_trace_log import ui_trace_mapping
from backend.models import (
    ClientLogEventRequest,
    ClientLogEventResponse,
    UiTraceEventRequest,
    UiTraceEventResponse,
)


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


@router.post("/ui-trace", response_model=UiTraceEventResponse)
async def log_ui_trace(payload: UiTraceEventRequest, request: Request) -> UiTraceEventResponse:
    ui_trace_logger = getattr(request.app.state, "ui_trace_log", None)
    if ui_trace_logger is not None:
        ui_trace_mapping(
            payload.surface,
            payload.phase,
            payload.event,
            payload.fields,
        )
        return UiTraceEventResponse(ok=True, logged=True)
    return UiTraceEventResponse(ok=True, logged=False, reason="logger_unavailable")
