from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import Settings
from app.errors import ErrorCode, current_request_id, error_response


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    retry_after: int = 0


class FixedWindowRateLimiter:
    """Pembatas laju in-memory per proses; cukup untuk pilot satu instance."""

    def __init__(self, *, window_seconds: int) -> None:
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int) -> RateLimitResult:
        now = time.monotonic()
        window_start = now - self.window_seconds
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= window_start:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, math.ceil(self.window_seconds - (now - hits[0])))
                return RateLimitResult(False, retry_after)
            hits.append(now)
        return RateLimitResult(True)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: Settings,
        limiter: FixedWindowRateLimiter,
    ) -> None:
        super().__init__(app)
        self.settings = settings
        self.limiter = limiter

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if path.startswith("/api/v1/health/"):
            return await call_next(request)

        if path.startswith("/api/v1/admin"):
            category = "admin"
            limit = self.settings.rate_limit_admin_per_minute
        elif path.startswith("/api/v1/chat"):
            category = "chat"
            limit = self.settings.rate_limit_chat_per_minute
        else:
            category = "public"
            limit = self.settings.rate_limit_public_per_minute

        client = request.client.host if request.client else "unknown"
        result = self.limiter.check(f"{category}:{client}", limit)
        if not result.allowed:
            return error_response(
                ErrorCode.RATE_LIMITED,
                "Terlalu banyak permintaan. Silakan coba lagi nanti.",
                429,
                current_request_id(request),
                {"Retry-After": str(result.retry_after)},
            )
        return await call_next(request)
