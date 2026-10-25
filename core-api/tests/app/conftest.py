from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import AdminCredential, Role, Settings
from app.main import create_app

SYSTEM_TOKEN = "system-admin-token-0123456789abcdef"
REVIEWER_TOKEN = "content-reviewer-token-0123456789"
HOSPITAL_TOKEN = "hospital-admin-token-0123456789"
HOSPITAL_ID = "rs-a"


def build_settings(tmp_path: Path, app_env: str = "test") -> Settings:
    return Settings(
        app_env=app_env,
        database_path=tmp_path / "rangkul-test.sqlite3",
        log_level="WARNING",
        cors_origins=("http://localhost:3000",),
        rate_limit_public_per_minute=1000,
        rate_limit_admin_per_minute=1000,
        rate_limit_chat_per_minute=1000,
        llm_provider="fake",
        admin_credentials=(
            AdminCredential(
                token=SYSTEM_TOKEN, name="Admin Sistem", role=Role.SYSTEM_ADMIN
            ),
            AdminCredential(
                token=REVIEWER_TOKEN, name="Reviewer Medis", role=Role.CONTENT_REVIEWER
            ),
            AdminCredential(
                token=HOSPITAL_TOKEN,
                name="Admin RS A",
                role=Role.HOSPITAL_ADMIN,
                hospital_id=HOSPITAL_ID,
            ),
        ),
    )


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return build_settings(tmp_path)


@pytest.fixture
def system_auth() -> dict[str, str]:
    return auth_header(SYSTEM_TOKEN)


@pytest.fixture
def reviewer_auth() -> dict[str, str]:
    return auth_header(REVIEWER_TOKEN)


@pytest.fixture
def hospital_auth() -> dict[str, str]:
    return auth_header(HOSPITAL_TOKEN)


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
