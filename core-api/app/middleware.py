from __future__ import annotations

import logging
import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from app.errors import ErrorCode, error_response
from app.logging_config import request_id_var

logger = logging.getLogger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Memberi request ID, mencatat metadata aman, dan menutup error tak terduga."""

    def __init__(self, app: ASGIApp, header_name: str = REQUEST_ID_HEADER) -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get(self.header_name, "")
        request_id = (
            incoming if _SAFE_REQUEST_ID.fullmatch(incoming) else str(uuid.uuid4())
        )
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        method = request.method
        path = request.url.path
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={"method": method, "path": path, "request_id": request_id},
            )
            failed = error_response(
                ErrorCode.INTERNAL_ERROR,
                "Terjadi kesalahan internal.",
                500,
                request_id,
            )
            failed.headers[self.header_name] = request_id
            return failed
        finally:
            request_id_var.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[self.header_name] = request_id
        logger.info(
            "request_completed",
            extra={
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
            },
        )
        return response
