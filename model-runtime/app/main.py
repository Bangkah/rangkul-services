from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger("rangkul")
MODEL_NAME = os.getenv("RANGKUL_MODEL", "rangkul-llm")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
MAX_BODY_BYTES, MAX_INPUT_CHARS, MAX_MESSAGES, MAX_OUTPUT_TOKENS = (
    128 * 1024,
    12_000,
    32,
    512,
)
ADMIN_PATHS = {"/api/pull", "/api/delete", "/api/create", "/api/copy", "/api/ps"}


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = MODEL_NAME
    messages: list[Message] = Field(min_length=1, max_length=MAX_MESSAGES)
    stream: Literal[True] = True
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("options")
    @classmethod
    def validate_options(cls, value):
        if set(value) - {"stop"}:
            raise ValueError("Only the stop option is accepted")
        return value

    @model_validator(mode="after")
    def validate_request(self):
        if self.model != MODEL_NAME:
            raise ValueError("Unknown model")
        if sum(len(m.content) for m in self.messages) > MAX_INPUT_CHARS:
            raise ValueError("Combined message content exceeds 12000 characters")
        return self


class AdmissionGate:
    def __init__(self):
        self.condition, self.active, self.waiting = asyncio.Condition(), False, 0
        self.queue_timeout = 30

    @asynccontextmanager
    async def slot(self):
        async with self.condition:
            if self.active and self.waiting >= 4:
                raise HTTPException(503, "Inference queue is full")
            queued = self.active
            if queued:
                self.waiting += 1
            try:
                await asyncio.wait_for(
                    self.condition.wait_for(lambda: not self.active), self.queue_timeout
                )
            except asyncio.TimeoutError:
                raise HTTPException(503, "Inference queue wait timed out")
            finally:
                if queued:
                    self.waiting -= 1
            self.active = True
        try:
            yield
        finally:
            async with self.condition:
                self.active = False
                self.condition.notify(1)


class RequestLimitsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if path in ADMIN_PATHS:
            return await JSONResponse(
                {"detail": "Ollama administration endpoints are disabled"},
                status_code=403,
            )(scope, receive, send)
        if path.startswith("/api/") and path != "/api/chat":
            return await JSONResponse({"detail": "Not Found"}, status_code=404)(
                scope, receive, send
            )
        headers = dict(scope.get("headers", []))
        try:
            if int(headers.get(b"content-length", b"0")) > MAX_BODY_BYTES:
                return await JSONResponse(
                    {"detail": "Request body exceeds 128 KiB"}, status_code=413
                )(scope, receive, send)
        except ValueError:
            return await JSONResponse(
                {"detail": "Invalid Content-Length"}, status_code=400
            )(scope, receive, send)
        body, more = bytearray(), True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY_BYTES:
                return await JSONResponse(
                    {"detail": "Request body exceeds 128 KiB"}, status_code=413
                )(scope, receive, send)
            more = message.get("more_body", False)
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ready = False
    app.state.model_info = None
    app.state.client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10)
    )
    app.state.gate = AdmissionGate()
    try:
        r = await app.state.client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        model = next(
            (
                m
                for m in r.json().get("models", [])
                if str(m.get("name", "")).split(":", 1)[0] == MODEL_NAME
            ),
            None,
        )
        if model is None:
            raise RuntimeError(f"Required Ollama model is unavailable: {MODEL_NAME}")
        app.state.model_info = model
        app.state.ready = True
        yield
    finally:
        app.state.ready = False
        await app.state.client.aclose()


app = FastAPI(
    title="RANGKUL AI Private Runtime",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(RequestLimitsMiddleware)


class OperationalLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        rid = headers.get(b"x-request-id", str(uuid.uuid4()).encode())[:128].decode(
            "latin-1"
        )
        started = time.monotonic()
        scope.setdefault("state", {})["request_id"] = rid
        status_code = 500

        async def logged_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", rid.encode("latin-1")))
                message["headers"] = response_headers
                duration_field = (
                    "response_headers_ms"
                    if scope.get("path") == "/api/chat"
                    else "duration_ms"
                )
                logger.info(
                    json.dumps(
                        {
                            "request_id": rid,
                            "path": scope.get("path", ""),
                            "status": status_code,
                            duration_field: round((time.monotonic() - started) * 1000),
                        }
                    )
                )
            await send(message)

        try:
            await self.app(scope, receive, logged_send)
        except Exception as exc:
            logger.error(
                json.dumps(
                    {
                        "request_id": rid,
                        "path": scope.get("path", ""),
                        "status": status_code,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        "error": type(exc).__name__,
                    }
                )
            )
            raise


app.add_middleware(OperationalLoggingMiddleware)


@app.get("/healthz")
async def healthz():
    return {"status": "alive"}


@app.get("/readyz")
async def readyz(request: Request):
    if not getattr(request.app.state, "ready", False):
        raise HTTPException(503, "Runtime is not ready")
    return {"status": "ready"}


async def proxy_stream(request: Request, payload: dict[str, Any]):
    if not getattr(request.app.state, "ready", False):
        raise HTTPException(503, "Runtime is not ready")
    payload["stream"], payload["model"] = True, MODEL_NAME
    stop = payload.get("options", {}).get("stop")
    payload["options"] = {
        "num_ctx": 4096,
        "num_predict": MAX_OUTPUT_TOKENS,
        "temperature": 0.1,
        "seed": 42,
        **({"stop": stop} if stop else {}),
    }
    gate_slot = request.app.state.gate.slot()
    await gate_slot.__aenter__()
    started = time.monotonic()
    try:
        upstream_request = request.app.state.client.build_request(
            "POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload
        )
        upstream = await request.app.state.client.send(upstream_request, stream=True)
        if upstream.status_code >= 400:
            await upstream.aclose()
            raise HTTPException(502, "Inference engine returned an error")
    except httpx.TimeoutException as exc:
        await gate_slot.__aexit__(type(exc), exc, exc.__traceback__)
        raise HTTPException(504, "Inference engine timed out") from None
    except httpx.HTTPError as exc:
        await gate_slot.__aexit__(type(exc), exc, exc.__traceback__)
        raise HTTPException(502, "Inference engine unavailable") from None
    except Exception:
        await gate_slot.__aexit__(None, None, None)
        raise

    async def output():
        try:
            async for chunk in upstream.aiter_bytes():
                if await request.is_disconnected():
                    break
                yield chunk
        except httpx.TimeoutException:
            logger.warning(
                json.dumps({"event": "upstream_timeout", "endpoint": "/api/chat"})
            )
            yield b'{"error":"Upstream timeout","done":true}\n'
        except httpx.HTTPError as exc:
            logger.error(
                json.dumps({"event": "upstream_error", "category": type(exc).__name__})
            )
            yield b'{"error":"Inference engine unavailable","done":true}\n'
        finally:
            await upstream.aclose()
            await gate_slot.__aexit__(None, None, None)
            logger.info(
                json.dumps(
                    {
                        "event": "inference_finished",
                        "request_id": getattr(
                            getattr(request, "state", None), "request_id", "unknown"
                        ),
                        "endpoint": "/api/chat",
                        "duration_ms": round((time.monotonic() - started) * 1000),
                    }
                )
            )

    return StreamingResponse(
        output(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    return await proxy_stream(request, body.model_dump())
