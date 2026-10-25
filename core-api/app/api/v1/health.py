from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import Database
from app.errors import AppError, ErrorCode, ErrorResponse

logger = logging.getLogger("app.health")

router = APIRouter(prefix="/health", tags=["Operasional"])


class HealthStatus(BaseModel):
    status: str


class ReadinessChecks(BaseModel):
    database: str


class ReadinessStatus(BaseModel):
    status: str
    checks: ReadinessChecks


@router.get(
    "/live",
    response_model=HealthStatus,
    summary="Liveness proses aplikasi",
)
def live() -> HealthStatus:
    return HealthStatus(status="alive")


@router.get(
    "/ready",
    response_model=ReadinessStatus,
    summary="Kesiapan dependensi wajib",
    responses={
        503: {
            "model": ErrorResponse,
            "description": "Dependensi wajib belum siap",
        }
    },
)
def ready(request: Request) -> ReadinessStatus:
    database: Database = request.app.state.db
    try:
        database.check_ready()
    except Exception as exc:
        logger.warning("readiness_failed", extra={"reason": type(exc).__name__})
        raise AppError(
            ErrorCode.SERVICE_UNAVAILABLE,
            "Layanan belum siap.",
            503,
        ) from None
    return ReadinessStatus(status="ready", checks=ReadinessChecks(database="ok"))
