from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

HOSPITAL_UPDATE_FIELDS = frozenset(
    {
        "name",
        "address",
        "latitude",
        "longitude",
        "contact_phone",
        "contact_email",
        "operating_hours",
        "source",
        "verified_at",
        "is_synthetic",
        "status",
    }
)
SERVICE_UPDATE_FIELDS = frozenset(
    {
        "name",
        "description",
        "requirements",
        "source",
        "verified_at",
        "is_synthetic",
        "status",
    }
)
VISIT_UPDATE_FIELDS = frozenset(
    {
        "title",
        "description",
        "sort_order",
        "source",
        "verified_at",
        "is_synthetic",
        "status",
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


def _update(
    connection: sqlite3.Connection,
    *,
    table: str,
    record_id: str,
    fields: Mapping[str, Any],
    allowed: frozenset[str],
    now: str,
) -> None:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Kolom tidak diizinkan: {sorted(unknown)}")
    assignments = [f"{name} = ?" for name in fields]
    assignments.append("updated_at = ?")
    values = [fields[name] for name in fields]
    values.extend([now, record_id])
    connection.execute(
        f"UPDATE {table} SET {', '.join(assignments)} WHERE id = ?", values
    )


def create_hospital(
    connection: sqlite3.Connection,
    *,
    hospital_id: str,
    data: Mapping[str, Any],
    now: str,
) -> dict[str, Any]:
    connection.execute(
        """INSERT INTO hospitals (
            id, name, address, latitude, longitude, contact_phone,
            contact_email, operating_hours, status, source, verified_at,
            is_synthetic, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)""",
        (
            hospital_id,
            data["name"],
            data.get("address", ""),
            data.get("latitude"),
            data.get("longitude"),
            data.get("contact_phone", ""),
            data.get("contact_email", ""),
            data.get("operating_hours", ""),
            data.get("source", ""),
            data.get("verified_at"),
            int(bool(data.get("is_synthetic", False))),
            now,
            now,
        ),
    )
    created = get_hospital(connection, hospital_id)
    if created is None:
        raise RuntimeError("Fasilitas gagal dibuat")
    return created


def get_hospital(
    connection: sqlite3.Connection,
    hospital_id: str,
    *,
    published_only: bool = False,
) -> dict[str, Any] | None:
    sql = "SELECT * FROM hospitals WHERE id = ?"
    params: list[Any] = [hospital_id]
    if published_only:
        sql += " AND status = 'published'"
    return _fetch(connection, sql, params)


def list_hospitals(
    connection: sqlite3.Connection,
    *,
    published_only: bool = False,
    status: str | None = None,
    hospital_id: str | None = None,
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
    if hospital_id:
        conditions.append("id = ?")
        params.append(hospital_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = connection.execute(
        f"SELECT COUNT(*) FROM hospitals {where}", params
    ).fetchone()[0]
    rows = _fetch_all(
        connection,
        f"""SELECT * FROM hospitals {where}
            ORDER BY name COLLATE NOCASE, id
            LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return rows, int(total)


def update_hospital(
    connection: sqlite3.Connection,
    hospital_id: str,
    fields: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any] | None:
    _update(
        connection,
        table="hospitals",
        record_id=hospital_id,
        fields=fields,
        allowed=HOSPITAL_UPDATE_FIELDS,
        now=now,
    )
    return get_hospital(connection, hospital_id)


def create_service(
    connection: sqlite3.Connection,
    *,
    service_id: str,
    hospital_id: str,
    data: Mapping[str, Any],
    now: str,
) -> dict[str, Any]:
    connection.execute(
        """INSERT INTO hospital_services (
            id, hospital_id, name, description, requirements, status, source,
            verified_at, is_synthetic, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)""",
        (
            service_id,
            hospital_id,
            data["name"],
            data.get("description", ""),
            data.get("requirements", ""),
            data.get("source", ""),
            data.get("verified_at"),
            int(bool(data.get("is_synthetic", False))),
            now,
            now,
        ),
    )
    created = get_service(connection, service_id)
    if created is None:
        raise RuntimeError("Layanan gagal dibuat")
    return created


def get_service(
    connection: sqlite3.Connection, service_id: str
) -> dict[str, Any] | None:
    return _fetch(
        connection, "SELECT * FROM hospital_services WHERE id = ?", [service_id]
    )


def list_services(
    connection: sqlite3.Connection,
    hospital_id: str,
    *,
    published_only: bool = False,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    conditions = ["s.hospital_id = ?"]
    params: list[Any] = [hospital_id]
    join = ""
    if published_only:
        conditions.extend(["s.status = 'published'", "h.status = 'published'"])
        join = "JOIN hospitals h ON h.id = s.hospital_id"
    elif status:
        conditions.append("s.status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}"

    total = connection.execute(
        f"""SELECT COUNT(*) FROM hospital_services s {join} {where}""", params
    ).fetchone()[0]
    rows = _fetch_all(
        connection,
        f"""SELECT s.* FROM hospital_services s {join} {where}
            ORDER BY s.name COLLATE NOCASE, s.id
            LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return rows, int(total)


def update_service(
    connection: sqlite3.Connection,
    service_id: str,
    fields: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any] | None:
    _update(
        connection,
        table="hospital_services",
        record_id=service_id,
        fields=fields,
        allowed=SERVICE_UPDATE_FIELDS,
        now=now,
    )
    return get_service(connection, service_id)


def create_visit_requirement(
    connection: sqlite3.Connection,
    *,
    requirement_id: str,
    hospital_id: str,
    data: Mapping[str, Any],
    now: str,
) -> dict[str, Any]:
    connection.execute(
        """INSERT INTO visit_requirements (
            id, hospital_id, title, description, sort_order, status, source,
            verified_at, is_synthetic, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)""",
        (
            requirement_id,
            hospital_id,
            data["title"],
            data.get("description", ""),
            data.get("sort_order", 0),
            data.get("source", ""),
            data.get("verified_at"),
            int(bool(data.get("is_synthetic", False))),
            now,
            now,
        ),
    )
    created = get_visit_requirement(connection, requirement_id)
    if created is None:
        raise RuntimeError("Persiapan kunjungan gagal dibuat")
    return created


def get_visit_requirement(
    connection: sqlite3.Connection, requirement_id: str
) -> dict[str, Any] | None:
    return _fetch(
        connection,
        "SELECT * FROM visit_requirements WHERE id = ?",
        [requirement_id],
    )


def list_visit_requirements(
    connection: sqlite3.Connection,
    hospital_id: str,
    *,
    published_only: bool = False,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    conditions = ["v.hospital_id = ?"]
    params: list[Any] = [hospital_id]
    join = ""
    if published_only:
        conditions.extend(["v.status = 'published'", "h.status = 'published'"])
        join = "JOIN hospitals h ON h.id = v.hospital_id"
    elif status:
        conditions.append("v.status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}"

    total = connection.execute(
        f"""SELECT COUNT(*) FROM visit_requirements v {join} {where}""", params
    ).fetchone()[0]
    rows = _fetch_all(
        connection,
        f"""SELECT v.* FROM visit_requirements v {join} {where}
            ORDER BY v.sort_order, v.title COLLATE NOCASE, v.id
            LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return rows, int(total)


def update_visit_requirement(
    connection: sqlite3.Connection,
    requirement_id: str,
    fields: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any] | None:
    _update(
        connection,
        table="visit_requirements",
        record_id=requirement_id,
        fields=fields,
        allowed=VISIT_UPDATE_FIELDS,
        now=now,
    )
    return get_visit_requirement(connection, requirement_id)
