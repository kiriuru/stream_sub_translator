from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ApiErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    recommended_action: str | None = None


class ApiErrorResponse(BaseModel):
    ok: bool = False
    error: ApiErrorPayload


class ApiException(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        recommended_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code or "UNKNOWN_ERROR").strip() or "UNKNOWN_ERROR"
        self.message = str(message or "Unexpected error.").strip() or "Unexpected error."
        self.status_code = int(status_code)
        self.details = dict(details or {})
        self.recommended_action = (
            str(recommended_action).strip() if recommended_action is not None and str(recommended_action).strip() else None
        )


def build_error_response(
    *,
    code: str,
    message: str,
    status_code: int = 400,
    details: dict[str, Any] | None = None,
    recommended_action: str | None = None,
) -> JSONResponse:
    payload = ApiErrorResponse(
        error=ApiErrorPayload(
            code=code,
            message=message,
            details=dict(details or {}),
            recommended_action=recommended_action,
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


async def api_exception_handler(_request: Request, exc: ApiException) -> JSONResponse:
    return build_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        recommended_action=exc.recommended_action,
    )


def register_api_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiException, api_exception_handler)
