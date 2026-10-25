from __future__ import annotations

import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app import articles, audit
from app.api.deps import AppSettings, DbConnection
from app.config import Role
from app.policy import (
    ensure_article_publishable,
    invalid,
    not_found,
    utc_now,
)
from app.schemas import (
    ArticleAdmin,
    ArticleCreate,
    ArticleUpdate,
    Page,
    PublicationStatus,
    StatusChangeRequest,
)
from app.security import Principal, require_roles

router = APIRouter(prefix="/admin", tags=["Admin - Artikel"])

ArticleEditor = Annotated[
    Principal,
    Depends(require_roles(Role.SYSTEM_ADMIN, Role.CONTENT_REVIEWER)),
]

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def _load(connection: sqlite3.Connection, article_id: str) -> dict[str, Any]:
    row = articles.get_article(connection, article_id)
    if row is None:
        raise not_found("Artikel tidak ditemukan.")
    return row


def _record(
    connection: sqlite3.Connection,
    principal: Principal,
    action: str,
    article_id: str,
    *,
    detail: str = "",
) -> None:
    audit.record_event(
        connection,
        actor=principal.name,
        actor_role=principal.role.value,
        action=action,
        object_type="article",
        object_id=article_id,
        detail=detail,
    )


@router.post(
    "/articles",
    response_model=ArticleAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Membuat artikel (selalu draft)",
)
def create_article(
    payload: ArticleCreate,
    connection: DbConnection,
    principal: ArticleEditor,
) -> dict[str, Any]:
    data = payload.model_dump()
    data["is_synthetic"] = int(payload.is_synthetic)
    row = articles.create_article(connection, data=data, now=utc_now().isoformat())
    _record(connection, principal, "create", row["id"])
    return row


@router.get(
    "/articles",
    response_model=Page[ArticleAdmin],
    summary="Daftar artikel untuk admin",
)
def list_articles(
    connection: DbConnection,
    principal: ArticleEditor,
    status_filter: Annotated[PublicationStatus | None, Query(alias="status")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    rows, total = articles.list_articles(
        connection,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/articles/{article_id}",
    response_model=ArticleAdmin,
    summary="Detail artikel untuk admin",
)
def get_article(
    article_id: str,
    connection: DbConnection,
    principal: ArticleEditor,
) -> dict[str, Any]:
    return _load(connection, article_id)


@router.patch(
    "/articles/{article_id}",
    response_model=ArticleAdmin,
    summary="Memperbarui artikel; artikel terbit kembali menjadi draft",
)
def update_article(
    article_id: str,
    payload: ArticleUpdate,
    connection: DbConnection,
    principal: ArticleEditor,
) -> dict[str, Any]:
    _load(connection, article_id)
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise invalid("Tidak ada perubahan yang dikirim.")
    if "is_synthetic" in fields:
        fields["is_synthetic"] = int(bool(fields["is_synthetic"]))
    fields["status"] = PublicationStatus.DRAFT.value
    fields["published_at"] = None
    row = articles.update_article(
        connection, article_id, fields, now=utc_now().isoformat()
    )
    if row is None:
        raise not_found("Artikel tidak ditemukan.")
    _record(
        connection,
        principal,
        "update",
        article_id,
        detail="Kolom: " + ", ".join(sorted(fields)),
    )
    return row


@router.post(
    "/articles/{article_id}/publish",
    response_model=ArticleAdmin,
    summary="Menerbitkan artikel bersumber",
)
def publish_article(
    article_id: str,
    connection: DbConnection,
    principal: ArticleEditor,
    settings: AppSettings,
) -> dict[str, Any]:
    row = _load(connection, article_id)
    if row["status"] == PublicationStatus.PUBLISHED.value:
        return row
    ensure_article_publishable(row, production=settings.is_production)
    now = utc_now().isoformat()
    updated = articles.update_article(
        connection,
        article_id,
        {"status": PublicationStatus.PUBLISHED.value, "published_at": now},
        now=now,
    )
    if updated is None:
        raise not_found("Artikel tidak ditemukan.")
    _record(connection, principal, "publish", article_id)
    return updated


@router.post(
    "/articles/{article_id}/archive",
    response_model=ArticleAdmin,
    summary="Mengarsipkan artikel",
)
def archive_article(
    article_id: str,
    payload: StatusChangeRequest,
    connection: DbConnection,
    principal: ArticleEditor,
) -> dict[str, Any]:
    row = _load(connection, article_id)
    if row["status"] == PublicationStatus.ARCHIVED.value:
        return row
    updated = articles.update_article(
        connection,
        article_id,
        {"status": PublicationStatus.ARCHIVED.value},
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Artikel tidak ditemukan.")
    _record(connection, principal, "archive", article_id, detail=payload.reason)
    return updated
