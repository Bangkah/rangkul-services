from app.config import Settings
from app.providers.base import (
    FakeLLMProvider,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMProviderRateLimited,
    LLMProviderResponseError,
    LLMProviderTimeout,
    LLMProviderUnavailable,
    LLMResult,
    MessageRole,
    UnavailableLLMProvider,
)
from app.providers.groq import GroqLLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "groq":
        return GroqLLMProvider(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            model=settings.groq_model,
            fallback_model=settings.groq_fallback_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    if settings.is_production:
        return UnavailableLLMProvider()
    return FakeLLMProvider()


__all__ = [
    "FakeLLMProvider",
    "GroqLLMProvider",
    "LLMMessage",
    "LLMProvider",
    "LLMProviderError",
    "LLMProviderRateLimited",
    "LLMProviderResponseError",
    "LLMProviderTimeout",
    "LLMProviderUnavailable",
    "LLMResult",
    "MessageRole",
    "UnavailableLLMProvider",
    "build_llm_provider",
]
