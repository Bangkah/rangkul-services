from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Sequence

from app import rag
from app.config import Settings
from app.errors import AppError, ErrorCode
from app.guardrails import (
    ABSTENTION_ANSWER,
    INJECTION_ANSWER,
    MEDICAL_ANSWER,
    PROVIDER_ANSWER,
    InputCategory,
    apply_output_guardrail,
    classify_input,
    crisis_answer,
)
from app.policy import invalid, parse_iso
from app.privacy import redact_pii
from app.prompts import SYSTEM_PROMPT_VERSION, build_context, build_messages
from app.providers import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    MessageRole,
)
from app.rag import RetrievedChunk
from app.schemas import (
    ChatHistoryMessage,
    ChatRequest,
    ChatResponse,
    ChatSafetyState,
    ChatSource,
)

logger = logging.getLogger("app.chat")


def _sources(chunks: Sequence[RetrievedChunk]) -> list[ChatSource]:
    seen: set[str] = set()
    sources: list[ChatSource] = []
    for chunk in chunks:
        if chunk.record_id in seen:
            continue
        seen.add(chunk.record_id)
        sources.append(
            ChatSource(
                source_id=chunk.record_id,
                document_id=chunk.document_id,
                title=chunk.title,
                version=chunk.version,
                published_at=parse_iso(chunk.published_at),
            )
        )
    return sources


def _history(
    history: Sequence[ChatHistoryMessage], *, max_turns: int
) -> list[LLMMessage]:
    if max_turns <= 0:
        return []
    selected = list(history)[-(max_turns * 2) :]
    return [
        LLMMessage(
            MessageRole(message.role),
            redact_pii(message.content).text,
        )
        for message in selected
    ]


def _consent_error() -> AppError:
    return AppError(
        ErrorCode.CONSENT_REQUIRED,
        "Persetujuan pemrosesan AI diperlukan sebelum chat dapat diproses.",
        403,
    )


def _provider_error() -> AppError:
    return AppError(
        ErrorCode.AI_PROVIDER_UNAVAILABLE,
        PROVIDER_ANSWER,
        503,
    )


def _response(
    *,
    request_id: str,
    session_id: str,
    answer: str,
    safety_state: ChatSafetyState,
    sources: Sequence[ChatSource] | None = None,
) -> ChatResponse:
    return ChatResponse(
        request_id=request_id,
        session_id=session_id,
        answer=answer,
        safety_state=safety_state,
        sources=list(sources or []),
        disclaimer=(
            "Informasi ini bukan diagnosis atau pengganti konsultasi tenaga kesehatan."
        ),
    )


async def run_chat(
    connection: sqlite3.Connection,
    settings: Settings,
    provider: LLMProvider,
    payload: ChatRequest,
    *,
    request_id: str,
) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise invalid("Pesan chat tidak boleh kosong.")
    if len(message) > settings.chat_max_message_chars:
        raise invalid("Pesan chat melebihi batas panjang yang diizinkan.")

    session_id = payload.session_id or f"sess-{uuid.uuid4()}"
    redacted = redact_pii(message)
    category = classify_input(redacted.text)

    if category is InputCategory.CRISIS:
        return _response(
            request_id=request_id,
            session_id=session_id,
            answer=crisis_answer(settings.crisis_contact),
            safety_state=ChatSafetyState.CRISIS,
        )
    if not payload.consent_ai_processing:
        raise _consent_error()
    if payload.consent_version != settings.ai_consent_version:
        raise _consent_error()
    if not settings.chat_enabled:
        raise _provider_error()
    if category is InputCategory.MEDICAL:
        return _response(
            request_id=request_id,
            session_id=session_id,
            answer=MEDICAL_ANSWER,
            safety_state=ChatSafetyState.MEDICAL_GUARDRAIL,
        )
    if category is InputCategory.INJECTION:
        return _response(
            request_id=request_id,
            session_id=session_id,
            answer=INJECTION_ANSWER,
            safety_state=ChatSafetyState.INJECTION_BLOCKED,
        )
    if not provider.available:
        raise _provider_error()

    rag.ensure_published_indexed(connection)
    chunks = rag.retrieve(
        connection,
        redacted.text,
        hospital_id=payload.hospital_id,
        top_k=settings.chat_top_k,
        threshold=settings.chat_similarity_threshold,
    )
    if not chunks:
        return _response(
            request_id=request_id,
            session_id=session_id,
            answer=ABSTENTION_ANSWER,
            safety_state=ChatSafetyState.ABSTAINED,
        )

    context, used_chunks = build_context(
        chunks, max_chars=settings.chat_max_context_chars
    )
    sources = _sources(used_chunks)
    messages = build_messages(
        context=context,
        history=_history(payload.history, max_turns=settings.chat_max_history_turns),
        question=redacted.text,
    )

    try:
        result = await provider.complete(
            messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    except LLMProviderError as exc:
        logger.warning(
            "chat_provider_failed",
            extra={
                "request_id": request_id,
                "provider": provider.name,
                "error_code": exc.code,
                "source_count": len(sources),
                "prompt_version": SYSTEM_PROMPT_VERSION,
            },
        )
        raise _provider_error() from exc

    guard = apply_output_guardrail(result.text, sources_present=bool(sources))
    if guard.replaced:
        sources = []
    response = _response(
        request_id=request_id,
        session_id=session_id,
        answer=guard.text,
        safety_state=ChatSafetyState(guard.safety_state),
        sources=sources,
    )
    logger.info(
        "chat_completed",
        extra={
            "request_id": request_id,
            "provider": provider.name,
            "model": result.model,
            "safety_state": response.safety_state.value,
            "source_count": len(response.sources),
            "prompt_version": SYSTEM_PROMPT_VERSION,
        },
    )
    return response
