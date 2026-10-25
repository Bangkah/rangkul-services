from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from app.api.deps import AppSettings, DbConnection, LlmProvider
from app.chat import run_chat
from app.errors import current_request_id
from app.policy import invalid
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["Chat"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _event(name: str, data: dict[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _tokens(text: str, size: int = 40) -> list[str]:
    return [text[start : start + size] for start in range(0, len(text), size)]


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat non-streaming berbasis sumber terbit",
)
async def chat_once(
    payload: ChatRequest,
    request: Request,
    connection: DbConnection,
    settings: AppSettings,
    provider: LlmProvider,
) -> ChatResponse:
    if payload.stream:
        raise invalid("Gunakan endpoint /api/v1/chat/stream untuk streaming.")
    return await run_chat(
        connection,
        settings,
        provider,
        payload,
        request_id=current_request_id(request),
    )


@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
    summary="Chat streaming SSE berbasis sumber terbit",
)
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    connection: DbConnection,
    settings: AppSettings,
    provider: LlmProvider,
) -> StreamingResponse:
    result = await run_chat(
        connection,
        settings,
        provider,
        payload,
        request_id=current_request_id(request),
    )

    async def events() -> AsyncIterator[str]:
        yield _event(
            "meta",
            {
                "request_id": result.request_id,
                "session_id": result.session_id,
            },
        )
        yield _event(
            "sources",
            {"sources": [source.model_dump(mode="json") for source in result.sources]},
        )
        for token in _tokens(result.answer):
            yield _event("token", {"text": token})
        yield _event(
            "done",
            {
                "status": "completed",
                "safety_state": result.safety_state.value,
            },
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
