from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.providers import (
    LLMMessage,
    LLMProviderRateLimited,
    LLMProviderResponseError,
    LLMProviderTimeout,
    LLMProviderUnavailable,
    MessageRole,
)
from app.providers.groq import GroqLLMProvider

API_KEY = "gsk-test-key-0123456789abcdef"
MESSAGES = [LLMMessage(role=MessageRole.USER, content="Apa persiapan tes HIV?")]


def _provider(handler, **overrides) -> GroqLLMProvider:
    values = {
        "api_key": API_KEY,
        "base_url": "https://groq.test/openai/v1",
        "model": "model-utama",
        "transport": httpx.MockTransport(handler),
    }
    values.update(overrides)
    return GroqLLMProvider(**values)


def test_placeholder_key_is_unavailable():
    provider = GroqLLMProvider(
        api_key="isi-dari-dashboard-groq",
        base_url="https://groq.test/openai/v1",
        model="model-utama",
    )

    assert provider.available is False
    with pytest.raises(LLMProviderUnavailable):
        asyncio.run(provider.complete(MESSAGES))


def test_successful_completion_sends_expected_request():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "model": "model-utama",
                "choices": [{"message": {"content": "Berdasarkan sumber terbit."}}],
            },
        )

    result = asyncio.run(_provider(handler).complete(MESSAGES, max_tokens=123))

    assert result.text == "Berdasarkan sumber terbit."
    assert result.model == "model-utama"
    request = captured[0]
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    body = json.loads(request.content)
    assert body["model"] == "model-utama"
    assert body["max_tokens"] == 123
    assert body["messages"] == [{"role": "user", "content": "Apa persiapan tes HIV?"}]


def test_fallback_model_is_used_after_server_error():
    models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        models.append(body["model"])
        if body["model"] == "model-utama":
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(
            200,
            json={
                "model": "model-cadangan",
                "choices": [{"message": {"content": "Jawaban cadangan dari sumber."}}],
            },
        )

    provider = _provider(
        handler,
        fallback_model="model-cadangan",
        max_retries=0,
    )
    result = asyncio.run(provider.complete(MESSAGES))

    assert models == ["model-utama", "model-cadangan"]
    assert result.model == "model-cadangan"


def test_rate_limit_raises_sanitized_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate"})

    provider = _provider(handler, max_retries=0)

    with pytest.raises(LLMProviderRateLimited):
        asyncio.run(provider.complete(MESSAGES))


def test_timeout_raises_sanitized_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    provider = _provider(handler, max_retries=0)

    with pytest.raises(LLMProviderTimeout):
        asyncio.run(provider.complete(MESSAGES))


def test_rejected_credentials_raise_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    provider = _provider(handler, max_retries=0)

    with pytest.raises(LLMProviderUnavailable):
        asyncio.run(provider.complete(MESSAGES))


def test_malformed_response_raises_response_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    provider = _provider(handler, max_retries=0)

    with pytest.raises(LLMProviderResponseError):
        asyncio.run(provider.complete(MESSAGES))
