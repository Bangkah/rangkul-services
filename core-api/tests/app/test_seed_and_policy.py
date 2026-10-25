from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import audit, seed
from app.config import Settings
from app.db import Database
from app.errors import AppError, ErrorCode
from app.main import create_app
from app.policy import (
    conflict,
    directions_url,
    ensure_synthetic_allowed,
    invalid,
    is_expired,
    not_found,
    parse_iso,
    publication_is_visible,
    to_iso,
    utc_now,
)


def test_directions_url_formats_coordinates_or_returns_none():
    assert directions_url(None, 1.0) is None
    assert directions_url(1.0, None) is None
    url = directions_url(-6.2, 106.816666)
    assert url is not None
    assert url.startswith("https://www.google.com/maps/dir/?api=1")
    assert "-6.200000,106.816666" in url


def test_time_normalisation_and_expiry():
    assert to_iso(None) is None
    assert to_iso(utc_now()).endswith("+00:00")
    with pytest.raises(AppError) as excinfo:
        to_iso(datetime(2026, 1, 1))
    assert excinfo.value.code is ErrorCode.VALIDATION_ERROR

    assert parse_iso(None) is None
    assert parse_iso("bukan-waktu") is None
    assert parse_iso("2026-01-01T00:00:00").tzinfo is not None
    assert is_expired(None) is False
    assert is_expired("2020-01-01T00:00:00+00:00") is True
    assert is_expired("2999-01-01T00:00:00+00:00") is False


def test_publication_visibility_rules():
    assert publication_is_visible("published", "2026-01-01T00:00:00+00:00") is True
    assert publication_is_visible("draft", "2026-01-01T00:00:00+00:00") is False
    assert publication_is_visible("published", None) is False
    assert (
        publication_is_visible(
            "published", "2026-01-01T00:00:00+00:00", "2020-01-01T00:00:00+00:00"
        )
        is False
    )


def test_safe_error_helpers_and_synthetic_guard():
    assert invalid("x").status_code == 422
    assert conflict("x").status_code == 409
    assert not_found("x").status_code == 404
    ensure_synthetic_allowed(False, production=True)
    with pytest.raises(AppError):
        ensure_synthetic_allowed(True, production=True)


def test_seed_is_idempotent_and_labelled(tmp_path):
    database = Database(tmp_path / "seed.sqlite3")
    database.migrate()

    with database.connect() as connection:
        first = seed.seed(connection, now="2026-10-01T00:00:00+00:00")
        connection.commit()
        second = seed.seed(connection)
        connection.commit()

        assert first == {"inserted": 9, "skipped": 0}
        assert second == {"inserted": 0, "skipped": 9}

        for table in (
            "hospitals",
            "hospital_services",
            "visit_requirements",
            "knowledge_documents",
            "articles",
        ):
            total = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            synthetic = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE is_synthetic = 1"
            ).fetchone()[0]
            assert total > 0
            assert synthetic == total

        source = connection.execute(
            "SELECT source FROM hospitals WHERE id = ?", (seed.SEED_HOSPITAL_ID,)
        ).fetchone()[0]
        assert "sintetis" in source.lower()
        draft_articles = connection.execute(
            "SELECT COUNT(*) FROM articles WHERE status = 'draft'"
        ).fetchone()[0]
        assert draft_articles == 1
        pending = connection.execute(
            "SELECT COUNT(*) FROM knowledge_documents WHERE status = 'pending_review'"
        ).fetchone()[0]
        assert pending == 1


def test_seed_data_is_visible_through_public_api(tmp_path):
    settings = Settings(
        app_env="test",
        database_path=tmp_path / "seed-api.sqlite3",
        log_level="WARNING",
        cors_origins=("http://localhost:3000",),
        admin_credentials=(),
    )
    database = Database(settings.database_path)
    database.migrate()
    with database.connect() as connection:
        seed.seed(connection)
        connection.commit()

    with TestClient(create_app(settings)) as client:
        hospitals = client.get("/api/v1/hospitals").json()
        assert hospitals["total"] == 1
        assert hospitals["items"][0]["id"] == seed.SEED_HOSPITAL_ID
        assert hospitals["items"][0]["is_synthetic"] is True
        assert (
            client.get(f"/api/v1/hospitals/{seed.SEED_HOSPITAL_ID}/services").json()[
                "total"
            ]
            == 2
        )
        assert (
            client.get(
                f"/api/v1/hospitals/{seed.SEED_HOSPITAL_ID}/visit-requirements"
            ).json()["total"]
            == 2
        )
        articles = client.get("/api/v1/articles").json()
        assert articles["total"] == 1
        assert articles["items"][0]["id"] == "article-demo-persiapan"


def test_seed_command_refuses_production(monkeypatch, tmp_path, capsys):
    database_path = tmp_path / "production.sqlite3"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv(
        "ADMIN_CREDENTIALS",
        json.dumps(
            [
                {
                    "token": "production-admin-token-0123456789abcdef",
                    "name": "Admin Produksi",
                    "role": "system_admin",
                }
            ]
        ),
    )

    assert seed.main() == 2
    assert not database_path.exists()
    assert "ditolak" in capsys.readouterr().err


def test_seed_command_writes_development_database(monkeypatch, tmp_path, capsys):
    database_path = tmp_path / "development.sqlite3"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))

    assert seed.main() == 0
    assert database_path.exists()
    assert "9 dibuat" in capsys.readouterr().out


def test_audit_detail_is_sanitised_and_truncated(tmp_path):
    database = Database(tmp_path / "audit.sqlite3")
    database.migrate()
    with database.connect() as connection:
        audit.record_event(
            connection,
            actor="Admin",
            actor_role="system_admin",
            action="create",
            object_type="hospital",
            object_id="rs-a",
            detail="  baris\n pertama\tkedua  ",
        )
        audit.record_event(
            connection,
            actor="Admin",
            actor_role="system_admin",
            action="update",
            object_type="hospital",
            object_id="rs-a",
            detail="x" * 1200,
        )
        connection.commit()

        rows, total = audit.list_events(
            connection, object_type="hospital", object_id="rs-a", limit=10, offset=0
        )
        assert total == 2
        assert rows[0]["detail"] == "x" * audit.MAX_DETAIL_LENGTH
        assert rows[1]["detail"] == "baris pertama kedua"

        filtered, filtered_total = audit.list_events(
            connection, action="create", limit=10, offset=0
        )
        assert filtered_total == 1
        assert filtered[0]["action"] == "create"
