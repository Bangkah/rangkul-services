from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import Database, MigrationError


def test_migrate_is_idempotent(tmp_path: Path):
    database = Database(tmp_path / "rangkul.sqlite3")

    assert database.migrate() == 1
    assert database.migrate() == 0
    assert database.pending_versions() == []

    with sqlite3.connect(database.path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(audit_events)")
        }
        versions = [
            row[0]
            for row in connection.execute("SELECT version FROM schema_migrations")
        ]

    assert {"id", "occurred_at", "actor", "actor_role", "action", "outcome"} <= columns
    assert versions == ["0001_audit_events"]


def test_pending_and_readiness_before_migration(tmp_path: Path):
    database = Database(tmp_path / "kosong.sqlite3")

    assert database.pending_versions() == ["0001_audit_events"]
    with pytest.raises(MigrationError):
        database.check_ready()


def test_broken_migration_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_contoh.sql").write_text(
        "CREATE TABLE contoh (id TEXT);", encoding="utf-8"
    )
    (migrations / "0002_rusak.sql").write_text("CREATE TABLE;", encoding="utf-8")
    monkeypatch.setattr("app.db.MIGRATIONS_DIR", migrations)
    database = Database(tmp_path / "rusak.sqlite3")

    with pytest.raises(MigrationError):
        database.migrate()

    with sqlite3.connect(database.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        versions = [
            row[0]
            for row in connection.execute("SELECT version FROM schema_migrations")
        ]

    assert "contoh" in tables
    assert versions == ["0001_contoh"]
    assert database.pending_versions() == ["0002_rusak"]


def test_invalid_migration_filename_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "migrasi-tanpa-nomor.sql").write_text("SELECT 1;", encoding="utf-8")
    monkeypatch.setattr("app.db.MIGRATIONS_DIR", migrations)

    with pytest.raises(MigrationError):
        Database(tmp_path / "db.sqlite3").migrate()


def test_unreadable_database_path(tmp_path: Path):
    directory = tmp_path / "bukan-database"
    directory.mkdir()

    with pytest.raises(MigrationError):
        Database(directory).check_ready()
