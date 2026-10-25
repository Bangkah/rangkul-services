from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Mapping
from typing import Any

KNOWLEDGE_UPDATE_FIELDS = frozenset(
    {
        "status",
        "reviewed_by",
        "reviewed_at",
        "review_reason",
        "published_at",
    }
)


def _fetch(
    connection: sqlite3.Connection, sql: str, params: list[Any]
) -> dict[str, Any] | None:
    row = connection.execute(sql, params).fetchone()
    return dict(row) if row is not None else None


def _fetch_all(
    connection: sqlite3.Connection, sql: str, params: list[Any]
) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, params).fetchall()]


def create_document(
    connection: sqlite3.Connection,
    *,
    document_id: str,
    title: str,
    source: str,
    owner: str,
    version: int,
    content: str,
    status: str,
    effective_from: str | None,
    review_due_at: str | None,
    previous_version_id: str | None,
    is_synthetic: bool,
    created_by: str,
    now: str,
) -> dict[str, Any]:
    record_id = str(uuid.uuid4())
    connection.execute(
        """INSERT INTO knowledge_documents (
            id, document_id, title, source, owner, version, status, content,
            effective_from, review_due_at, previous_version_id, is_synthetic,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record_id,
            document_id,
            title,
            source,
            owner,
            version,
            status,
            content,
            effective_from,
            review_due_at,
            previous_version_id,
            int(bool(is_synthetic)),
            created_by,
            now,
            now,
        ),
    )
    created = get_document(connection, record_id)
    if created is None:
        raise RuntimeError("Dokumen pengetahuan gagal dibuat")
    return created


def get_document(
    connection: sqlite3.Connection, record_id: str
) -> dict[str, Any] | None:
    return _fetch(
        connection,
        "SELECT * FROM knowledge_documents WHERE id = ?",
        [record_id],
    )


def next_version(connection: sqlite3.Connection, document_id: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM knowledge_documents "
        "WHERE document_id = ?",
        [document_id],
    ).fetchone()
    return int(row[0])


def list_documents(
    connection: sqlite3.Connection,
    *,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    conditions: list[str] = []
    params: list[Any] = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = connection.execute(
        f"SELECT COUNT(*) FROM knowledge_documents {where}", params
    ).fetchone()[0]
    rows = _fetch_all(
        connection,
        f"""SELECT * FROM knowledge_documents {where}
            ORDER BY updated_at DESC, document_id, version DESC
            LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return rows, int(total)


def update_document(
    connection: sqlite3.Connection,
    record_id: str,
    fields: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any] | None:
    unknown = set(fields) - KNOWLEDGE_UPDATE_FIELDS
    if unknown:
        raise ValueError(f"Kolom tidak diizinkan: {sorted(unknown)}")
    assignments = [f"{name} = ?" for name in fields]
    values = [fields[name] for name in fields]
    assignments.append("updated_at = ?")
    values.extend([now, record_id])
    connection.execute(
        f"UPDATE knowledge_documents SET {', '.join(assignments)} WHERE id = ?",
        values,
    )
    return get_document(connection, record_id)


def supersede_published(
    connection: sqlite3.Connection,
    *,
    document_id: str,
    keep_id: str,
    now: str,
) -> list[dict[str, Any]]:
    rows = _fetch_all(
        connection,
        """SELECT * FROM knowledge_documents
           WHERE document_id = ? AND status = 'published' AND id <> ?""",
        [document_id, keep_id],
    )
    if rows:
        connection.execute(
            """UPDATE knowledge_documents
               SET status = 'archived', updated_at = ?
               WHERE document_id = ? AND status = 'published' AND id <> ?""",
            [now, document_id, keep_id],
        )
    return rows
