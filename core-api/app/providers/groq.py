from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import httpx

from app.providers.base import (
    LLMMessage,
    LLMProviderError,
    LLMProviderRateLimited,
    LLMProviderResponseError,
    LLMProviderTimeout,
    LLMProviderUnavailable,
    LLMResult,
)

logger = logging.getLogger("app.providers.groq")

_PLACEHOLDER_KEYS = {
    "isi-dari-dashboard-groq",
    "ganti-dengan-api-key",
    "changeme",
}


def _is_configured_key(api_key: str) -> bool:
    key = api_key.strip()
    if len(key) < 20:
        return False
    lowered = key.lower()
    if lowered in _PLACEHOLDER_KEYS:
        return False
    return not lowered.startswith(("isi-", "ganti-", "example", "changeme"))


class GroqLLMProvider:
    name = "groq"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        fallback_model: str = "",
        timeout_seconds: float = 20.0,
        max_retries: int = 1,
        retry_backoff_seconds: float = 0.2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self.available = _is_configured_key(self._api_key)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.fallback_model = fallback_model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._transport = transport

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> LLMResult:
        if not self.available:
            raise LLMProviderUnavailable("Kredensial Groq belum dikonfigurasi.")
        models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)

        last_error: LLMProviderError | None = None
        for index, model in enumerate(models):
            try:
                return await self._complete_model(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except LLMProviderError as exc:
                last_error = exc
                if index == len(models) - 1:
                    raise
        raise last_error or LLMProviderUnavailable("Provider LLM gagal.")

    async def _complete_model(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResult:
        body = {
            "model": model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.max_retries + 1):
            status: int | None = None
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=body,
                    )
                status = response.status_code
                if response.status_code == 200:
                    result = self._parse(response)
                    logger.info(
                        "llm_completed",
                        extra={
                            "model": result.model,
                            "attempt": attempt,
                            "status": status,
                        },
                    )
                    return result
                if response.status_code in {401, 403}:
                    raise LLMProviderUnavailable("Kredensial provider ditolak.")
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        await self._backoff(attempt)
                        continue
                    raise LLMProviderRateLimited("Batas penggunaan provider tercapai.")
                if response.status_code >= 500:
                    if attempt < self.max_retries:
                        await self._backoff(attempt)
                        continue
                    raise LLMProviderResponseError(
                        "Provider mengembalikan kesalahan server."
                    )
                raise LLMProviderResponseError("Provider menolak permintaan.")
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    await self._backoff(attempt)
                    continue
                logger.warning(
                    "llm_timeout",
                    extra={"model": model, "attempt": attempt},
                )
                raise LLMProviderTimeout("Provider melewati batas waktu.") from exc
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    await self._backoff(attempt)
                    continue
                logger.warning(
                    "llm_unreachable",
                    extra={"model": model, "attempt": attempt},
                )
                raise LLMProviderUnavailable("Provider tidak dapat dihubungi.") from exc
            except ValueError as exc:
                raise LLMProviderResponseError(
                    "Respons provider tidak dapat dibaca."
                ) from exc
            finally:
                if status is not None and status != 200:
                    logger.warning(
                        "llm_failed",
                        extra={
                            "model": model,
                            "attempt": attempt,
                            "status": status,
                        },
                    )

        raise LLMProviderResponseError("Provider tidak mengembalikan jawaban.")

    async def _backoff(self, attempt: int) -> None:
        delay = self.retry_backoff_seconds * (2**attempt)
        if delay > 0:
            await asyncio.sleep(delay)

    @staticmethod
    def _parse(response: httpx.Response) -> LLMResult:
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise LLMProviderResponseError("Respons provider bukan JSON.") from exc
        if not isinstance(payload, dict):
            raise LLMProviderResponseError("Respons provider tidak valid.")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProviderResponseError("Respons provider tanpa pilihan.")
        first = choices[0]
        if not isinstance(first, dict):
            raise LLMProviderResponseError("Respons provider tidak valid.")
        message = first.get("message")
        if not isinstance(message, dict):
            raise LLMProviderResponseError("Respons provider tanpa pesan.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderResponseError("Respons provider kosong.")
        model = payload.get("model")
        return LLMResult(
            text=content.strip(),
            model=model if isinstance(model, str) and model else "groq",
        )
