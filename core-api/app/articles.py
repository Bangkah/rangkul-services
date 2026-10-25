from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Mapping
from typing import Any

ARTICLE_UPDATE_FIELDS = frozenset(
    {
        "title",
        "summary",
        "content",
        "source",
        "reference_url",
        "status",
        "published_at",
        "is_synthetic",
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


def create_article(
    connection: sqlite3.Connection,
    *,
    data: Mapping[str, Any],
    now: str,
) -> dict[str, Any]:
    article_id = str(uuid.uuid4())
    connection.execute(
        """INSERT INTO articles (
            id, title, summary, content, source, reference_url, status,
            is_synthetic, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)""",
        (
            article_id,
            data["title"],
            data.get("summary", ""),
            data.get("content", ""),
            data.get("source", ""),
            data.get("reference_url", ""),
            int(bool(data.get("is_synthetic", False))),
            now,
            now,
        ),
    )
    created = get_article(connection, article_id)
    if created is None:
        raise RuntimeError("Artikel gagal dibuat")
    return created


def get_article(
    connection: sqlite3.Connection,
    article_id: str,
    *,
    published_only: bool = False,
) -> dict[str, Any] | None:
    sql = "SELECT * FROM articles WHERE id = ?"
    params: list[Any] = [article_id]
    if published_only:
        sql += " AND status = 'published'"
    return _fetch(connection, sql, params)


def list_articles(
    connection: sqlite3.Connection,
    *,
    published_only: bool = False,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    conditions: list[str] = []
    params: list[Any] = []
    if published_only:
        conditions.append("status = 'published'")
    elif status:
        conditions.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = connection.execute(
        f"SELECT COUNT(*) FROM articles {where}", params
    ).fetchone()[0]
    rows = _fetch_all(
        connection,
        f"""SELECT * FROM articles {where}
            ORDER BY published_at IS NULL, published_at DESC, title COLLATE NOCASE
            LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return rows, int(total)


def update_article(
    connection: sqlite3.Connection,
    article_id: str,
    fields: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any] | None:
    unknown = set(fields) - ARTICLE_UPDATE_FIELDS
    if unknown:
        raise ValueError(f"Kolom tidak diizinkan: {sorted(unknown)}")
    assignments = [f"{name} = ?" for name in fields]
    values = [fields[name] for name in fields]
    assignments.append("updated_at = ?")
    values.extend([now, article_id])
    connection.execute(
        f"UPDATE articles SET {', '.join(assignments)} WHERE id = ?", values
    )
    return get_article(connection, article_id)
