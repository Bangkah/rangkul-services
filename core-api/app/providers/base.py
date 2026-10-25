"""Kontrak adapter penyedia LLM. Implementasi Groq ditambahkan pada Fase 2."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True, slots=True)
class LLMResult:
    text: str
    model: str


class LLMProviderError(RuntimeError):
    """Kegagalan provider yang sudah disanitasi untuk pemanggil."""

    code = "provider_error"


class LLMProviderUnavailable(LLMProviderError):
    code = "provider_unavailable"


class LLMProviderTimeout(LLMProviderError):
    code = "provider_timeout"


class LLMProviderRateLimited(LLMProviderError):
    code = "provider_rate_limited"


class LLMProviderResponseError(LLMProviderError):
    code = "provider_response_error"


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    available: bool

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> LLMResult: ...


class UnavailableLLMProvider:
    name = "unavailable"
    available = False

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> LLMResult:
        raise LLMProviderUnavailable("Provider LLM tidak dikonfigurasi.")


class FakeLLMProvider:
    """Provider tiruan deterministik untuk pengujian tanpa panggilan jaringan."""

    name = "fake"
    available = True

    def __init__(
        self,
        reply: str = "Jawaban uji dari provider tiruan.",
        model: str = "fake-model",
        error: LLMProviderError | None = None,
    ) -> None:
        self.reply = reply
        self.model = model
        self.error = error
        self.calls: list[tuple[LLMMessage, ...]] = []

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> LLMResult:
        self.calls.append(tuple(messages))
        if self.error is not None:
            raise self.error
        return LLMResult(text=self.reply, model=self.model)
