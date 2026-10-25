from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

DEFAULT_DATABASE_PATH = Path("data/rangkul.sqlite3")
DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_AI_CONSENT_VERSION = "privacy-notice-v1"
ALLOWED_ENVIRONMENTS = {"development", "test", "staging", "production"}
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
ALLOWED_LLM_PROVIDERS = {"fake", "groq"}
PLACEHOLDER_TOKEN_PREFIXES = ("dev-", "ganti-", "changeme", "isi-", "example")
PRODUCTION_MIN_TOKEN_LENGTH = 32


class Role(str, Enum):
    SYSTEM_ADMIN = "system_admin"
    CONTENT_REVIEWER = "content_reviewer"
    HOSPITAL_ADMIN = "hospital_admin"


@dataclass(frozen=True, slots=True)
class AdminCredential:
    token: str = field(repr=False)
    name: str
    role: Role
    hospital_id: str | None = None


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    database_path: Path
    log_level: str
    cors_origins: tuple[str, ...]
    admin_credentials: tuple[AdminCredential, ...]
    llm_provider: str = "fake"
    groq_api_key: str = field(default="", repr=False)
    groq_base_url: str = DEFAULT_GROQ_BASE_URL
    groq_model: str = DEFAULT_GROQ_MODEL
    groq_fallback_model: str = ""
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 1
    llm_temperature: float = 0.1
    llm_max_tokens: int = 600
    chat_enabled: bool = True
    chat_max_message_chars: int = 2000
    chat_max_history_turns: int = 6
    chat_top_k: int = 4
    chat_similarity_threshold: float = 0.2
    chat_max_context_chars: int = 6000
    ai_consent_version: str = DEFAULT_AI_CONSENT_VERSION
    crisis_contact: str = ""
    rate_limit_public_per_minute: int = 120
    rate_limit_admin_per_minute: int = 60
    rate_limit_chat_per_minute: int = 10
    rate_limit_window_seconds: int = 60

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if env is None else env
        app_env = values.get("APP_ENV", "development").strip().lower()
        if app_env not in ALLOWED_ENVIRONMENTS:
            raise ValueError(
                f"APP_ENV harus salah satu dari {sorted(ALLOWED_ENVIRONMENTS)}"
            )

        log_level = values.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in ALLOWED_LOG_LEVELS:
            raise ValueError(
                f"LOG_LEVEL harus salah satu dari {sorted(ALLOWED_LOG_LEVELS)}"
            )

        database_path = Path(
            values.get("DATABASE_PATH", "").strip() or DEFAULT_DATABASE_PATH
        )

        raw_origins = values.get("CORS_ORIGINS", "").strip()
        cors_origins = tuple(
            origin.strip()
            for origin in (
                raw_origins.split(",") if raw_origins else DEFAULT_CORS_ORIGINS
            )
            if origin.strip()
        )
        if not cors_origins:
            raise ValueError("CORS_ORIGINS tidak boleh kosong")

        credentials = _parse_admin_credentials(values.get("ADMIN_CREDENTIALS", ""))
        if not credentials and app_env == "development":
            credentials = (
                AdminCredential(
                    token="dev-system-admin-token",
                    name="Admin Pengembangan",
                    role=Role.SYSTEM_ADMIN,
                ),
            )
        if app_env == "production":
            _validate_production_credentials(credentials)

        llm_provider = values.get("LLM_PROVIDER", "fake").strip().lower()
        if llm_provider not in ALLOWED_LLM_PROVIDERS:
            raise ValueError(
                f"LLM_PROVIDER harus salah satu dari {sorted(ALLOWED_LLM_PROVIDERS)}"
            )
        groq_base_url = values.get("GROQ_BASE_URL", "").strip() or DEFAULT_GROQ_BASE_URL
        ai_consent_version = (
            values.get("AI_CONSENT_VERSION", "").strip() or DEFAULT_AI_CONSENT_VERSION
        )

        return cls(
            app_env=app_env,
            database_path=database_path,
            log_level=log_level,
            cors_origins=cors_origins,
            admin_credentials=credentials,
            llm_provider=llm_provider,
            groq_api_key=values.get("GROQ_API_KEY", "").strip(),
            groq_base_url=groq_base_url.rstrip("/"),
            groq_model=(values.get("GROQ_MODEL", "").strip() or DEFAULT_GROQ_MODEL),
            groq_fallback_model=values.get("GROQ_FALLBACK_MODEL", "").strip(),
            llm_timeout_seconds=_read_float(
                values, "LLM_TIMEOUT_SECONDS", 20.0, 1.0, 120.0
            ),
            llm_max_retries=_read_int(values, "LLM_MAX_RETRIES", 1, 0, 3),
            llm_temperature=_read_float(values, "LLM_TEMPERATURE", 0.1, 0.0, 2.0),
            llm_max_tokens=_read_int(values, "LLM_MAX_TOKENS", 600, 50, 4000),
            chat_enabled=_read_bool(values, "CHAT_ENABLED", True),
            chat_max_message_chars=_read_int(
                values, "CHAT_MAX_MESSAGE_CHARS", 2000, 1, 4000
            ),
            chat_max_history_turns=_read_int(values, "CHAT_HISTORY_TURNS", 6, 0, 20),
            chat_top_k=_read_int(values, "CHAT_TOP_K", 4, 1, 20),
            chat_similarity_threshold=_read_float(
                values, "CHAT_SIMILARITY_THRESHOLD", 0.2, 0.0, 1.0
            ),
            chat_max_context_chars=_read_int(
                values, "CHAT_MAX_CONTEXT_CHARS", 6000, 500, 50000
            ),
            ai_consent_version=ai_consent_version,
            crisis_contact=values.get("CRISIS_CONTACT", "").strip(),
            rate_limit_public_per_minute=_read_int(
                values, "RATE_LIMIT_PUBLIC_PER_MINUTE", 120, 1, 100000
            ),
            rate_limit_admin_per_minute=_read_int(
                values, "RATE_LIMIT_ADMIN_PER_MINUTE", 60, 1, 100000
            ),
            rate_limit_chat_per_minute=_read_int(
                values, "RATE_LIMIT_CHAT_PER_MINUTE", 10, 1, 100000
            ),
            rate_limit_window_seconds=_read_int(
                values, "RATE_LIMIT_WINDOW_SECONDS", 60, 1, 3600
            ),
        )


def _parse_admin_credentials(raw: str) -> tuple[AdminCredential, ...]:
    if not raw.strip():
        return ()
    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "ADMIN_CREDENTIALS harus berupa JSON array berisi objek kredensial"
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError("ADMIN_CREDENTIALS harus berupa JSON array")

    credentials: list[AdminCredential] = []
    seen_tokens: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("Setiap kredensial admin harus berupa objek")
        token = item.get("token")
        name = item.get("name")
        role = item.get("role")
        hospital_id = item.get("hospital_id")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("token admin wajib diisi")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name admin wajib diisi")
        try:
            parsed_role = Role(role)
        except ValueError as exc:
            raise ValueError(f"role admin tidak dikenal: {role!r}") from exc
        if hospital_id is not None and not isinstance(hospital_id, str):
            raise ValueError("hospital_id admin harus berupa teks atau null")
        if parsed_role is Role.HOSPITAL_ADMIN and not (hospital_id or "").strip():
            raise ValueError("hospital_admin wajib memiliki hospital_id")
        if token in seen_tokens:
            raise ValueError("Token admin tidak boleh duplikat")
        seen_tokens.add(token)
        credentials.append(
            AdminCredential(
                token=token,
                name=name.strip(),
                role=parsed_role,
                hospital_id=(hospital_id or "").strip() or None,
            )
        )
    return tuple(credentials)


def _read_bool(values: Mapping[str, str], name: str, default: bool) -> bool:
    raw = values.get(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "ya", "on"}:
        return True
    if raw in {"0", "false", "no", "tidak", "off"}:
        return False
    raise ValueError(f"{name} harus berupa boolean")


def _read_int(
    values: Mapping[str, str], name: str, default: int, minimum: int, maximum: int
) -> int:
    raw = values.get(name, "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} harus berupa bilangan bulat") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} harus antara {minimum} dan {maximum}")
    return parsed


def _read_float(
    values: Mapping[str, str],
    name: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    raw = values.get(name, "").strip()
    if not raw:
        return default
    try:
        parsed = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} harus berupa angka") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} harus antara {minimum} dan {maximum}")
    return parsed


def _validate_production_credentials(
    credentials: tuple[AdminCredential, ...],
) -> None:
    if not credentials:
        raise ValueError(
            "ADMIN_CREDENTIALS wajib dikonfigurasi pada lingkungan produksi"
        )
    for credential in credentials:
        if len(credential.token) < PRODUCTION_MIN_TOKEN_LENGTH:
            raise ValueError(
                "Token admin produksi minimal 32 karakter dan tidak boleh placeholder"
            )
        if credential.token.lower().startswith(PLACEHOLDER_TOKEN_PREFIXES):
            raise ValueError(
                "Token placeholder pengembangan tidak boleh dipakai di produksi"
            )
