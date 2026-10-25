from __future__ import annotations

import asyncio

from app.providers import (
    FakeLLMProvider,
    LLMMessage,
    LLMProvider,
    MessageRole,
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
