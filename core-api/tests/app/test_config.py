from __future__ import annotations

import json

import pytest

from app.config import AdminCredential, Role, Settings


def test_development_default_has_dev_admin():
    settings = Settings.from_env({"APP_ENV": "development"})

    assert settings.app_env == "development"
    assert settings.database_path.name == "rangkul.sqlite3"
    assert settings.cors_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    assert settings.admin_credentials[0].role is Role.SYSTEM_ADMIN


def test_settings_can_be_read_from_process_environment(monkeypatch):
    for name in (
        "APP_ENV",
        "DATABASE_PATH",
        "LOG_LEVEL",
        "CORS_ORIGINS",
        "ADMIN_CREDENTIALS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("LOG_LEVEL", "warning")

    settings = Settings.from_env()

    assert settings.app_env == "staging"
    assert settings.log_level == "WARNING"
    assert settings.admin_credentials == ()


def test_credentials_are_parsed_with_scope():
    raw = json.dumps(
        [
            {
                "token": "token-sistem-panjang-sekali",
                "name": "Admin Sistem",
                "role": "system_admin",
            },
            {
                "token": "token-rs-a-panjang-sekali",
                "name": "Admin RS A",
                "role": "hospital_admin",
                "hospital_id": "rs-a",
            },
        ]
    )

    settings = Settings.from_env({"ADMIN_CREDENTIALS": raw, "LOG_LEVEL": "debug"})

    assert settings.log_level == "DEBUG"
    assert [credential.role for credential in settings.admin_credentials] == [
        Role.SYSTEM_ADMIN,
        Role.HOSPITAL_ADMIN,
    ]
    assert settings.admin_credentials[1].hospital_id == "rs-a"


@pytest.mark.parametrize(
    "credentials",
    [
        "bukan-json",
        json.dumps({"token": "x"}),
        json.dumps([{"token": "", "name": "A", "role": "system_admin"}]),
        json.dumps([{"token": "x", "name": "", "role": "system_admin"}]),
        json.dumps([{"token": "x", "name": "A", "role": "super_admin"}]),
        json.dumps(
            [{"token": "x", "name": "A", "role": "hospital_admin"}],
        ),
        json.dumps(
            [
                {"token": "x", "name": "A", "role": "system_admin"},
                {"token": "x", "name": "B", "role": "content_reviewer"},
            ]
        ),
        json.dumps(
            [{"token": "x", "name": "A", "role": "system_admin", "hospital_id": 7}]
        ),
        json.dumps(["bukan-objek"]),
    ],
)
def test_invalid_credentials_are_rejected(credentials: str):
    with pytest.raises(ValueError):
        Settings.from_env({"ADMIN_CREDENTIALS": credentials})


def test_production_requires_strong_non_placeholder_credentials():
    with pytest.raises(ValueError):
        Settings.from_env({"APP_ENV": "production"})

    with pytest.raises(ValueError):
        Settings.from_env(
            {
                "APP_ENV": "production",
                "ADMIN_CREDENTIALS": json.dumps(
                    [{"token": "pendek", "name": "A", "role": "system_admin"}]
                ),
            }
        )

    with pytest.raises(ValueError):
        Settings.from_env(
            {
                "APP_ENV": "production",
                "ADMIN_CREDENTIALS": json.dumps(
                    [
                        {
                            "token": "dev-system-admin-token-0123456789abcdef",
                            "name": "A",
                            "role": "system_admin",
                        }
                    ]
                ),
            }
        )

    valid = Settings.from_env(
        {
            "APP_ENV": "production",
            "ADMIN_CREDENTIALS": json.dumps(
                [{"token": "p" * 32, "name": "A", "role": "system_admin"}]
            ),
        }
    )
    assert valid.is_production


@pytest.mark.parametrize(
    "env",
    [
        {"APP_ENV": "pabrik"},
        {"LOG_LEVEL": "VERBOSE"},
        {"CORS_ORIGINS": " , "},
    ],
)
def test_invalid_environment_values_are_rejected(env):
    merged = {"APP_ENV": "development", **env}
    with pytest.raises(ValueError):
        Settings.from_env(merged)


def test_credential_repr_never_exposes_token():
    credential = AdminCredential(
        token="rahasia-sekali-token", name="Admin", role=Role.SYSTEM_ADMIN
    )

    assert "rahasia-sekali-token" not in repr(credential)
    assert "Admin" in repr(credential)
