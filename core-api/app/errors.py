from __future__ import annotations

import logging
from collections.abc import Mapping
from enum import Enum
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import request_id_var

logger = logging.getLogger("app.errors")


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    RATE_LIMITED = "RATE_LIMITED"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    KNOWLEDGE_UNAVAILABLE = "KNOWLEDGE_UNAVAILABLE"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


_STATUS_CODES: Mapping[int, tuple[ErrorCode, str]] = {
    400: (ErrorCode.VALIDATION_ERROR, "Permintaan tidak valid."),
    401: (ErrorCode.UNAUTHORIZED, "Autentikasi diperlukan."),
    403: (ErrorCode.FORBIDDEN, "Akses ditolak."),
    404: (ErrorCode.NOT_FOUND, "Sumber daya tidak ditemukan."),
    405: (ErrorCode.METHOD_NOT_ALLOWED, "Metode tidak diizinkan."),
    429: (ErrorCode.RATE_LIMITED, "Terlalu banyak permintaan."),
    503: (ErrorCode.SERVICE_UNAVAILABLE, "Layanan belum siap."),
}


class AppError(Exception):
    """Kesalahan yang aman ditampilkan ke klien."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.headers = dict(headers or {})


def current_request_id(request: Request | None = None) -> str:
    if request is not None:
        value = getattr(request.state, "request_id", None)
        if isinstance(value, str) and value:
            return value
    return request_id_var.get()


def error_response(
    code: ErrorCode,
    message: str,
    status_code: int,
    request_id: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code.value,
                "message": message,
                "request_id": request_id,
            }
        },
        headers=dict(headers or {}),
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
        error = cast(AppError, exc)
        if error.status_code >= 500:
            logger.warning(
                "app_error",
                extra={"request_id": current_request_id(request)},
            )
        return error_response(
            error.code,
            error.message,
            error.status_code,
            current_request_id(request),
            error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(
            ErrorCode.VALIDATION_ERROR,
            "Permintaan tidak valid.",
            422,
            current_request_id(request),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: Exception) -> JSONResponse:
        http_error = cast(StarletteHTTPException, exc)
        code, message = _STATUS_CODES.get(
            http_error.status_code, (ErrorCode.INTERNAL_ERROR, "Terjadi kesalahan.")
        )
        headers = getattr(http_error, "headers", None) or {}
        return error_response(
            code,
            message,
            http_error.status_code,
            current_request_id(request),
            headers,
        )
