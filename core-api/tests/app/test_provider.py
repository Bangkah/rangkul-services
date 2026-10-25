from __future__ import annotations

import asyncio

from app.config import AdminCredential, Role, Settings
from app.providers import (
    FakeLLMProvider,
    GroqLLMProvider,
    LLMMessage,
    LLMProvider,
    MessageRole,
    UnavailableLLMProvider,
    build_llm_provider,
)


def test_fake_provider_is_deterministic_and_records_messages():
    provider = FakeLLMProvider(reply="Jawaban terkurasi.", model="fake-1")
    messages = [LLMMessage(role=MessageRole.USER, content="Apa itu HIV?")]

    result = asyncio.run(provider.complete(messages))

    assert isinstance(provider, LLMProvider)
    assert result.text == "Jawaban terkurasi."
    assert result.model == "fake-1"
    assert provider.calls == [tuple(messages)]


def test_message_roles_match_provider_contract():
    assert {role.value for role in MessageRole} == {"system", "user", "assistant"}


def _settings(tmp_path, *, app_env: str = "test", provider: str = "fake"):
    return Settings(
        app_env=app_env,
        database_path=tmp_path / "provider.sqlite3",
        log_level="WARNING",
        cors_origins=("http://localhost:3000",),
        admin_credentials=(
            AdminCredential(
                token="system-admin-token-0123456789abcdef",
                name="Admin",
                role=Role.SYSTEM_ADMIN,
            ),
        ),
        llm_provider=provider,
        groq_api_key="gsk-test-key-0123456789abcdef",
    )


def test_build_llm_provider_uses_fake_outside_production(tmp_path):
    provider = build_llm_provider(_settings(tmp_path))

    assert isinstance(provider, FakeLLMProvider)


def test_build_llm_provider_fails_closed_in_production(tmp_path):
    provider = build_llm_provider(
        _settings(tmp_path, app_env="production", provider="fake")
    )

    assert isinstance(provider, UnavailableLLMProvider)
    assert provider.available is False


def test_build_llm_provider_selects_groq(tmp_path):
    provider = build_llm_provider(_settings(tmp_path, provider="groq"))

    assert isinstance(provider, GroqLLMProvider)
    assert provider.available is True
