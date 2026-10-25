from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import Database
from app.main import create_app


def test_live_returns_200_without_database(client):
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert response.headers["X-Request-ID"]


def test_ready_confirms_migrated_database(client):
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_startup_applies_migrations(settings):
    app = create_app(settings)
    with TestClient(app):
        pass

    with sqlite3.connect(settings.database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        applied = [
            row[0]
            for row in connection.execute("SELECT version FROM schema_migrations")
        ]

    assert {"audit_events", "hospitals", "articles"} <= tables
    assert "schema_migrations" in tables
    assert applied == [
        "0001_audit_events",
        "0002_catalog_and_content",
        "0003_chat_rag",
    ]


def test_ready_fails_softly_on_unmigrated_database(client, tmp_path: Path):
    client.app.state.db = Database(tmp_path / "belum-dimigrasi.sqlite3")

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert body["error"]["message"] == "Layanan belum siap."
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "sqlite" not in response.text.lower()


def test_liveness_does_not_depend_on_database(client, tmp_path: Path):
    broken = tmp_path / "direktori"
    broken.mkdir()
    client.app.state.db = Database(broken)

    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/health/ready").status_code == 503
