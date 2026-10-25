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
ALLOWED_ENVIRONMENTS = {"development", "test", "staging", "production"}
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
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

        return cls(
            app_env=app_env,
            database_path=database_path,
            log_level=log_level,
            cors_origins=cors_origins,
            admin_credentials=credentials,
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
