from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("app.db")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_MIGRATION_NAME = re.compile(r"^\d{4}_[a-z0-9_]+$")


class MigrationError(RuntimeError):
    """Migrasi gagal diterapkan."""


class Database:
    """Akses SQLite terkontrol dan runner migrasi SQL bernomor."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def migration_files(self) -> list[Path]:
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for path in files:
            if not _MIGRATION_NAME.fullmatch(path.stem):
                raise MigrationError(f"Nama migrasi tidak valid: {path.name}")
        return files

    def applied_versions(self, connection: sqlite3.Connection) -> set[str]:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )"""
        )
        connection.commit()
        rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
        return {str(row["version"]) for row in rows}

    def migrate(self) -> int:
        files = self.migration_files()
        applied_count = 0
        with self.connect() as connection:
            applied = self.applied_versions(connection)
            for path in files:
                version = path.stem
                if version in applied:
                    continue
                sql = path.read_text(encoding="utf-8")
                applied_at = datetime.now(timezone.utc).isoformat()
                safe_version = version.replace("'", "''")
                script = (
                    "BEGIN;\n"
                    f"{sql}\n"
                    "INSERT INTO schema_migrations (version, applied_at) "
                    f"VALUES ('{safe_version}', '{applied_at}');\n"
                    "COMMIT;"
                )
                try:
                    connection.executescript(script)
                except sqlite3.Error as exc:
                    connection.rollback()
                    raise MigrationError(f"Migrasi {version} gagal: {exc}") from exc
                applied_count += 1
                logger.info("migration_applied", extra={"version": version})
        return applied_count

    def pending_versions(self) -> list[str]:
        with self.connect() as connection:
            applied = self.applied_versions(connection)
        return [
            path.stem for path in self.migration_files() if path.stem not in applied
        ]

    def check_ready(self) -> None:
        try:
            with self.connect() as connection:
                connection.execute("SELECT 1").fetchone()
                applied = self.applied_versions(connection)
        except sqlite3.Error as exc:
            raise MigrationError("Database tidak dapat diakses") from exc
        pending = [
            path.stem for path in self.migration_files() if path.stem not in applied
        ]
        if pending:
            raise MigrationError("Database belum dimigrasikan sepenuhnya")
