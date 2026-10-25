from __future__ import annotations

import sqlite3
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app import audit, knowledge
from app.api.deps import AppSettings, DbConnection
from app.config import Role
from app.policy import (
    conflict,
    ensure_knowledge_publishable,
    invalid,
    is_expired,
    not_found,
    to_iso,
    utc_now,
)
from app.schemas import (
    KnowledgeDocumentAdmin,
    KnowledgeDocumentCreate,
    KnowledgeReviewRequest,
    KnowledgeStatus,
    Page,
    ReviewDecision,
    StatusChangeRequest,
)
from app.security import Principal, require_roles

router = APIRouter(prefix="/admin", tags=["Admin - Pengetahuan"])

KnowledgeEditor = Annotated[
    Principal,
    Depends(require_roles(Role.SYSTEM_ADMIN, Role.CONTENT_REVIEWER)),
]

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def _view(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "is_expired": is_expired(row.get("review_due_at"))}


def _load(connection: sqlite3.Connection, record_id: str) -> dict[str, Any]:
    row = knowledge.get_document(connection, record_id)
    if row is None:
        raise not_found("Dokumen pengetahuan tidak ditemukan.")
    return row


def _record(
    connection: sqlite3.Connection,
    principal: Principal,
    action: str,
    record: dict[str, Any],
    *,
    detail: str = "",
) -> None:
    audit.record_event(
        connection,
        actor=principal.name,
        actor_role=principal.role.value,
        action=action,
        object_type="knowledge_document",
        object_id=record["id"],
        version=str(record["version"]),
        detail=detail,
    )


@router.post(
    "/knowledge-documents",
    response_model=KnowledgeDocumentAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Membuat dokumen pengetahuan (draft/pending review)",
)
def create_document(
    payload: KnowledgeDocumentCreate,
    connection: DbConnection,
    principal: KnowledgeEditor,
) -> dict[str, Any]:
    previous: dict[str, Any] | None = None
    if payload.previous_version_id:
        previous = _load(connection, payload.previous_version_id)
        document_id = previous["document_id"]
        version = knowledge.next_version(connection, document_id)
    else:
        document_id = str(uuid.uuid4())
        version = 1

    now = utc_now().isoformat()
    try:
        row = knowledge.create_document(
            connection,
            document_id=document_id,
            title=payload.title,
            source=payload.source,
            owner=payload.owner,
            version=version,
            content=payload.content,
            status=(
                KnowledgeStatus.PENDING_REVIEW.value
                if payload.submit_for_review
                else KnowledgeStatus.DRAFT.value
            ),
            effective_from=to_iso(payload.effective_from),
            review_due_at=to_iso(payload.review_due_at),
            previous_version_id=payload.previous_version_id,
            is_synthetic=payload.is_synthetic,
            created_by=principal.name,
            now=now,
        )
    except sqlite3.IntegrityError:
        raise conflict("Versi dokumen sudah dibuat oleh permintaan lain.") from None
    _record(connection, principal, "create", row)
    return _view(row)


@router.get(
    "/knowledge-documents",
    response_model=Page[KnowledgeDocumentAdmin],
    summary="Daftar dan status dokumen pengetahuan",
)
def list_documents(
    connection: DbConnection,
    principal: KnowledgeEditor,
    status_filter: Annotated[KnowledgeStatus | None, Query(alias="status")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    rows, total = knowledge.list_documents(
        connection,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [_view(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/knowledge-documents/{record_id}",
    response_model=KnowledgeDocumentAdmin,
    summary="Detail dokumen pengetahuan",
)
def get_document(
    record_id: str,
    connection: DbConnection,
    principal: KnowledgeEditor,
) -> dict[str, Any]:
    return _view(_load(connection, record_id))


@router.post(
    "/knowledge-documents/{record_id}/submit-review",
    response_model=KnowledgeDocumentAdmin,
    summary="Mengajukan dokumen untuk peninjauan",
)
def submit_for_review(
    record_id: str,
    connection: DbConnection,
    principal: KnowledgeEditor,
) -> dict[str, Any]:
    row = _load(connection, record_id)
    if row["status"] == KnowledgeStatus.PENDING_REVIEW.value:
        return _view(row)
    if row["status"] not in {
        KnowledgeStatus.DRAFT.value,
        KnowledgeStatus.REJECTED.value,
    }:
        raise conflict("Dokumen pada status ini tidak dapat diajukan peninjauan.")
    updated = knowledge.update_document(
        connection,
        record_id,
        {
            "status": KnowledgeStatus.PENDING_REVIEW.value,
            "reviewed_by": None,
            "reviewed_at": None,
            "review_reason": "",
        },
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Dokumen pengetahuan tidak ditemukan.")
    _record(connection, principal, "submit_review", updated)
    return _view(updated)


@router.post(
    "/knowledge-documents/{record_id}/review",
    response_model=KnowledgeDocumentAdmin,
    summary="Menyetujui atau menolak dokumen",
)
def review_document(
    record_id: str,
    payload: KnowledgeReviewRequest,
    connection: DbConnection,
    principal: KnowledgeEditor,
) -> dict[str, Any]:
    row = _load(connection, record_id)
    if payload.decision is ReviewDecision.REJECT and not payload.reason.strip():
        raise invalid("Alasan penolakan wajib diisi.")

    target = (
        KnowledgeStatus.APPROVED
        if payload.decision is ReviewDecision.APPROVE
        else KnowledgeStatus.REJECTED
    )
    if row["status"] == target.value:
        return _view(row)
    if row["status"] != KnowledgeStatus.PENDING_REVIEW.value:
        raise conflict("Hanya dokumen pending_review yang dapat ditinjau.")

    reason = payload.reason.strip()
    if not reason:
        reason = "Disetujui untuk diterbitkan."
    updated = knowledge.update_document(
        connection,
        record_id,
        {
            "status": target.value,
            "reviewed_by": principal.name,
            "reviewed_at": utc_now().isoformat(),
            "review_reason": reason,
        },
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Dokumen pengetahuan tidak ditemukan.")
    _record(
        connection,
        principal,
        "review_approve"
        if payload.decision is ReviewDecision.APPROVE
        else "review_reject",
        updated,
        detail=reason,
    )
    return _view(updated)


@router.post(
    "/knowledge-documents/{record_id}/publish",
    response_model=KnowledgeDocumentAdmin,
    summary="Menerbitkan versi dokumen yang telah disetujui",
)
def publish_document(
    record_id: str,
    connection: DbConnection,
    principal: KnowledgeEditor,
    settings: AppSettings,
) -> dict[str, Any]:
    row = _load(connection, record_id)
    if row["status"] == KnowledgeStatus.PUBLISHED.value:
        return _view(row)
    ensure_knowledge_publishable(row, production=settings.is_production)

    now = utc_now().isoformat()
    updated = knowledge.update_document(
        connection,
        record_id,
        {
            "status": KnowledgeStatus.PUBLISHED.value,
            "published_at": now,
        },
        now=now,
    )
    if updated is None:
        raise not_found("Dokumen pengetahuan tidak ditemukan.")

    superseded = knowledge.supersede_published(
        connection,
        document_id=row["document_id"],
        keep_id=record_id,
        now=now,
    )
    for old in superseded:
        _record(
            connection,
            principal,
            "archive_superseded",
            old,
            detail=f"Digantikan oleh versi {row['version']}.",
        )
    _record(connection, principal, "publish", updated)
    return _view(updated)


@router.post(
    "/knowledge-documents/{record_id}/archive",
    response_model=KnowledgeDocumentAdmin,
    summary="Mengarsipkan dokumen",
)
def archive_document(
    record_id: str,
    payload: StatusChangeRequest,
    connection: DbConnection,
    principal: KnowledgeEditor,
) -> dict[str, Any]:
    row = _load(connection, record_id)
    if row["status"] == KnowledgeStatus.ARCHIVED.value:
        return _view(row)
    if row["status"] not in {
        KnowledgeStatus.APPROVED.value,
        KnowledgeStatus.PUBLISHED.value,
        KnowledgeStatus.REJECTED.value,
    }:
        raise conflict("Dokumen pada status ini tidak dapat diarsipkan.")
    updated = knowledge.update_document(
        connection,
        record_id,
        {"status": KnowledgeStatus.ARCHIVED.value},
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Dokumen pengetahuan tidak ditemukan.")
    _record(connection, principal, "archive", updated, detail=payload.reason)
    return _view(updated)


@router.post(
    "/knowledge-documents/{record_id}/revoke",
    response_model=KnowledgeDocumentAdmin,
    summary="Mencabut dokumen yang telah terbit",
)
def revoke_document(
    record_id: str,
    payload: StatusChangeRequest,
    connection: DbConnection,
    principal: KnowledgeEditor,
) -> dict[str, Any]:
    row = _load(connection, record_id)
    if row["status"] == KnowledgeStatus.REVOKED.value:
        return _view(row)
    if row["status"] != KnowledgeStatus.PUBLISHED.value:
        raise conflict("Hanya dokumen terbit yang dapat dicabut.")
    updated = knowledge.update_document(
        connection,
        record_id,
        {"status": KnowledgeStatus.REVOKED.value},
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Dokumen pengetahuan tidak ditemukan.")
    _record(connection, principal, "revoke", updated, detail=payload.reason)
    return _view(updated)
