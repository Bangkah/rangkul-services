from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from app.policy import utc_now

MAX_DETAIL_LENGTH = 1000


def record_event(
    connection: sqlite3.Connection,
    *,
    actor: str,
    actor_role: str,
    action: str,
    object_type: str,
    object_id: str = "",
    version: str = "",
    outcome: str = "success",
    detail: str = "",
) -> None:
    safe_detail = " ".join(detail.split())[:MAX_DETAIL_LENGTH]
    connection.execute(
        """INSERT INTO audit_events (
            id, occurred_at, actor, actor_role, action, object_type,
            object_id, version, outcome, detail
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            utc_now().isoformat(),
            actor,
            actor_role,
            action,
            object_type,
            object_id,
            version,
            outcome,
            safe_detail,
        ),
    )


def list_events(
    connection: sqlite3.Connection,
    *,
    object_type: str | None = None,
    object_id: str | None = None,
    action: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    conditions: list[str] = []
    params: list[Any] = []
    if object_type:
        conditions.append("object_type = ?")
        params.append(object_type)
    if object_id:
        conditions.append("object_id = ?")
        params.append(object_id)
    if action:
        conditions.append("action = ?")
        params.append(action)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = connection.execute(
        f"SELECT COUNT(*) FROM audit_events {where}", params
    ).fetchone()[0]
    rows = connection.execute(
        f"""SELECT * FROM audit_events {where}
            ORDER BY occurred_at DESC, rowid DESC
            LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    return [dict(row) for row in rows], int(total)
