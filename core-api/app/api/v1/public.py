from __future__ import annotations

import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Query

from app import articles, catalog
from app.api.deps import DbConnection
from app.policy import directions_url, not_found
from app.schemas import (
    ArticlePublic,
    HospitalPublic,
    Page,
    ServicePublic,
    VisitRequirementPublic,
)

router = APIRouter(tags=["Publik"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def _hospital_or_404(
    connection: sqlite3.Connection, hospital_id: str
) -> dict[str, Any]:
    row = catalog.get_hospital(connection, hospital_id, published_only=True)
    if row is None:
        raise not_found("Fasilitas tidak ditemukan atau belum dipublikasikan.")
    return row


@router.get(
    "/hospitals",
    response_model=Page[HospitalPublic],
    summary="Daftar fasilitas yang dipublikasikan",
)
def list_hospitals(
    connection: DbConnection,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    rows, total = catalog.list_hospitals(
        connection, published_only=True, limit=limit, offset=offset
    )
    return {
        "items": [
            {**row, "directions_url": directions_url(row["latitude"], row["longitude"])}
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/hospitals/{hospital_id}",
    response_model=HospitalPublic,
    summary="Detail fasilitas terpublikasi",
)
def get_hospital(hospital_id: str, connection: DbConnection) -> dict[str, Any]:
    row = _hospital_or_404(connection, hospital_id)
    return {
        **row,
        "directions_url": directions_url(row["latitude"], row["longitude"]),
    }


@router.get(
    "/hospitals/{hospital_id}/services",
    response_model=Page[ServicePublic],
    summary="Layanan terverifikasi pada fasilitas",
)
def list_hospital_services(
    hospital_id: str,
    connection: DbConnection,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    _hospital_or_404(connection, hospital_id)
    rows, total = catalog.list_services(
        connection,
        hospital_id,
        published_only=True,
        limit=limit,
        offset=offset,
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/hospitals/{hospital_id}/visit-requirements",
    response_model=Page[VisitRequirementPublic],
    summary="Persiapan kunjungan yang telah dikonfirmasi",
)
def list_visit_requirements(
    hospital_id: str,
    connection: DbConnection,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    _hospital_or_404(connection, hospital_id)
    rows, total = catalog.list_visit_requirements(
        connection,
        hospital_id,
        published_only=True,
        limit=limit,
        offset=offset,
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/articles",
    response_model=Page[ArticlePublic],
    summary="Daftar artikel terpublikasi",
)
def list_articles(
    connection: DbConnection,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    rows, total = articles.list_articles(
        connection, published_only=True, limit=limit, offset=offset
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/articles/{article_id}",
    response_model=ArticlePublic,
    summary="Detail artikel terpublikasi",
)
def get_article(article_id: str, connection: DbConnection) -> dict[str, Any]:
    row = articles.get_article(connection, article_id, published_only=True)
    if row is None:
        raise not_found("Artikel tidak ditemukan atau belum dipublikasikan.")
    return row
