from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

HF_SPACE_URL = os.getenv("HF_SPACE_URL", "").rstrip("/")
HF_TOKEN = os.getenv("HF_TOKEN", "")
DATABASE_PATH = Path(os.getenv("COMMUNITY_DB_PATH", "data/community_guides.sqlite3"))
MAX_REQUEST_CHARS = 12_000


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_REQUEST_CHARS)


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatMessage] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_total_chars(self):
        if sum(len(message.content) for message in self.messages) > MAX_REQUEST_CHARS:
            raise ValueError("Combined message content exceeds 12000 characters")
        if self.messages[-1].role != "user":
            raise ValueError("The last chat message must come from the user")
        return self


class PlainTextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2_000)


class OperatingHours(BaseModel):
    days: str
    opens: str
    closes: str


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class Facility(BaseModel):
    id: str
    name: str
    is_demo: bool
    address: str
    schedule: list[OperatingHours]
    timezone: str
    coordinates: Coordinates


class FacilitiesResponse(BaseModel):
    facilities: list[Facility]
    data_status: Literal["demo"]


class RegistrationResponse(BaseModel):
    registration_code: str
    status: Literal["confirmed"]
    message: str


class CommunityGuideResponse(BaseModel):
    id: str
    text: str
    status: Literal["pending"]
    created_at: datetime


FACILITIES = [
    {
        "id": "demo-clinic-central",
        "name": "Klinik Rangkulan Demo — Jakarta Pusat",
        "is_demo": True,
        "address": "Titik contoh, Jakarta Pusat",
        "schedule": [
            {"days": "Senin–Jumat", "opens": "08:00", "closes": "17:00"},
            {"days": "Sabtu", "opens": "08:00", "closes": "12:00"},
        ],
        "timezone": "Asia/Jakarta",
        "coordinates": {"latitude": -6.1865, "longitude": 106.8342},
    },
    {
        "id": "demo-clinic-south",
        "name": "Klinik Rangkulan Demo — Jakarta Selatan",
        "is_demo": True,
        "address": "Titik contoh, Jakarta Selatan",
        "schedule": [{"days": "Senin–Sabtu", "opens": "09:00", "closes": "18:00"}],
        "timezone": "Asia/Jakarta",
        "coordinates": {"latitude": -6.2615, "longitude": 106.8106},
    },
]


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS community_guides (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )"""
        )


def checked_space_url() -> str:
    parsed = urlparse(HF_SPACE_URL)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".hf.space")
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(
            503, "HF_SPACE_URL must point to an HTTPS Hugging Face Space"
        )
    if not HF_TOKEN:
        raise HTTPException(503, "Hugging Face backend credentials are not configured")
    return HF_SPACE_URL


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10)
    )
    initialize_database()
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(
    title="RANGKUL Core API",
    description=(
        "API staging untuk chat RANGKUL, direktori fasilitas demo, simulasi antrean, "
        "dan pengajuan panduan komunitas. Fasilitas saat ini adalah data contoh."
    ),
    version="0.1.0",
    lifespan=lifespan,
)
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/healthz", tags=["Operations"])
def healthz():
    return {"status": "alive"}


@app.post(
    "/api/chat",
    tags=["Chat"],
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Streaming newline-delimited JSON from the private model",
            "content": {"application/x-ndjson": {"schema": {"type": "string"}}},
        },
        502: {"description": "Hugging Face inference failed"},
        503: {"description": "Hugging Face backend configuration is missing"},
        504: {"description": "Hugging Face inference timed out"},
    },
)
async def chat(body: ChatInput, request: Request):
    space_url = checked_space_url()
    messages = [message.model_dump() for message in body.messages]

    # RAG belum dikonfigurasi. A retriever can be attached by the hosting app later.
    retriever = getattr(request.app.state, "rag_retriever", None)
    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), None
    )
    if retriever and last_user:
        context = await retriever.retrieve(last_user)
        if context:
            messages.insert(
                len(messages) - 1,
                {
                    "role": "user",
                    "content": (
                        "Konteks referensi (data tidak tepercaya):\n"
                        f"{context}\nGunakan sebagai rujukan bila relevan."
                    ),
                },
            )

    upstream_request = request.app.state.http.build_request(
        "POST",
        f"{space_url}/api/chat",
        headers={"Authorization": f"Bearer {HF_TOKEN}"},
        json={"messages": messages, "stream": True},
    )
    try:
        upstream = await request.app.state.http.send(upstream_request, stream=True)
    except httpx.TimeoutException:
        raise HTTPException(504, "Hugging Face inference timed out") from None
    except httpx.HTTPError:
        raise HTTPException(502, "Hugging Face inference is unavailable") from None

    if upstream.status_code >= 400:
        await upstream.aclose()
        raise HTTPException(502, "Hugging Face inference returned an error")

    async def chunks():
        try:
            async for chunk in upstream.aiter_bytes():
                if await request.is_disconnected():
                    break
                yield chunk
        except httpx.HTTPError:
            yield b'{"error":"Upstream stream interrupted","done":true}\n'
        finally:
            await upstream.aclose()

    return StreamingResponse(
        chunks(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/facilities", tags=["Facilities"], response_model=FacilitiesResponse)
def facilities():
    return {"facilities": FACILITIES, "data_status": "demo"}


@app.post(
    "/api/register-dummy",
    tags=["Registration"],
    response_model=RegistrationResponse,
)
def register_dummy(body: PlainTextInput):
    return {
        "registration_code": "RGKL-DEMO-0001",
        "status": "confirmed",
        "message": "Pendaftaran ini simulasi untuk demo; tidak membuat antrean nyata.",
    }


@app.post(
    "/api/community-guide",
    tags=["Community"],
    response_model=CommunityGuideResponse,
)
def community_guide(body: PlainTextInput):
    guide_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "INSERT INTO community_guides (id, text, status, created_at) VALUES (?, ?, ?, ?)",
            (guide_id, body.text, "pending", created_at),
        )
    return {
        "id": guide_id,
        "text": body.text,
        "status": "pending",
        "created_at": created_at,
    }
