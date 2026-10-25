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


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> LLMResult: ...


class FakeLLMProvider:
    """Provider tiruan deterministik untuk pengujian tanpa panggilan jaringan."""

    name = "fake"

    def __init__(
        self,
        reply: str = "Jawaban uji dari provider tiruan.",
        model: str = "fake-model",
    ) -> None:
        self.reply = reply
        self.model = model
        self.calls: list[tuple[LLMMessage, ...]] = []

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> LLMResult:
        self.calls.append(tuple(messages))
        return LLMResult(text=self.reply, model=self.model)
