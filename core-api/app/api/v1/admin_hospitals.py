from __future__ import annotations

import sqlite3
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app import audit, catalog
from app.api.deps import AppSettings, DbConnection
from app.config import Role
from app.policy import (
    conflict,
    ensure_hospital_publishable,
    ensure_service_publishable,
    ensure_visit_requirement_publishable,
    invalid,
    not_found,
    to_iso,
    utc_now,
)
from app.schemas import (
    HospitalAdmin,
    HospitalCreate,
    HospitalUpdate,
    Page,
    PublicationStatus,
    ServiceAdmin,
    ServiceCreate,
    ServiceUpdate,
    StatusChangeRequest,
    VisitRequirementAdmin,
    VisitRequirementCreate,
    VisitRequirementUpdate,
)
from app.security import Principal, ensure_hospital_scope, require_roles

router = APIRouter(prefix="/admin", tags=["Admin - Fasilitas"])

HospitalEditor = Annotated[
    Principal,
    Depends(require_roles(Role.SYSTEM_ADMIN, Role.HOSPITAL_ADMIN)),
]
SystemAdmin = Annotated[Principal, Depends(require_roles(Role.SYSTEM_ADMIN))]

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def _load_hospital(
    connection: sqlite3.Connection, hospital_id: str, principal: Principal
) -> dict[str, Any]:
    row = catalog.get_hospital(connection, hospital_id)
    if row is None:
        raise not_found("Fasilitas tidak ditemukan.")
    ensure_hospital_scope(principal, hospital_id)
    return row


def _load_service(
    connection: sqlite3.Connection, service_id: str, principal: Principal
) -> dict[str, Any]:
    row = catalog.get_service(connection, service_id)
    if row is None:
        raise not_found("Layanan tidak ditemukan.")
    ensure_hospital_scope(principal, row["hospital_id"])
    return row


def _load_requirement(
    connection: sqlite3.Connection, requirement_id: str, principal: Principal
) -> dict[str, Any]:
    row = catalog.get_visit_requirement(connection, requirement_id)
    if row is None:
        raise not_found("Persiapan kunjungan tidak ditemukan.")
    ensure_hospital_scope(principal, row["hospital_id"])
    return row


def _record(
    connection: sqlite3.Connection,
    principal: Principal,
    action: str,
    object_type: str,
    object_id: str,
    *,
    detail: str = "",
    version: str = "",
) -> None:
    audit.record_event(
        connection,
        actor=principal.name,
        actor_role=principal.role.value,
        action=action,
        object_type=object_type,
        object_id=object_id,
        version=version,
        detail=detail,
    )


def _normalise_update(fields: dict[str, Any], *, reset_published: bool) -> None:
    if not fields:
        raise invalid("Tidak ada perubahan yang dikirim.")
    if "verified_at" in fields:
        fields["verified_at"] = to_iso(fields["verified_at"])
    if "is_synthetic" in fields:
        fields["is_synthetic"] = int(bool(fields["is_synthetic"]))
    fields["status"] = PublicationStatus.DRAFT.value
    if reset_published and "verified_at" not in fields:
        fields["verified_at"] = None


@router.post(
    "/hospitals",
    response_model=HospitalAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Membuat fasilitas (selalu draft)",
)
def create_hospital(
    payload: HospitalCreate,
    connection: DbConnection,
    principal: SystemAdmin,
) -> dict[str, Any]:
    now = utc_now().isoformat()
    data = payload.model_dump()
    data["verified_at"] = to_iso(payload.verified_at)
    data["is_synthetic"] = int(payload.is_synthetic)
    try:
        row = catalog.create_hospital(
            connection, hospital_id=payload.id, data=data, now=now
        )
    except sqlite3.IntegrityError:
        raise conflict("ID fasilitas sudah digunakan.") from None
    _record(connection, principal, "create", "hospital", payload.id)
    return row


@router.get(
    "/hospitals",
    response_model=Page[HospitalAdmin],
    summary="Daftar fasilitas untuk admin",
)
def list_hospitals(
    connection: DbConnection,
    principal: HospitalEditor,
    status_filter: Annotated[PublicationStatus | None, Query(alias="status")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    scope = principal.hospital_id if principal.role is Role.HOSPITAL_ADMIN else None
    rows, total = catalog.list_hospitals(
        connection,
        status=status_filter.value if status_filter else None,
        hospital_id=scope,
        limit=limit,
        offset=offset,
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/hospitals/{hospital_id}",
    response_model=HospitalAdmin,
    summary="Detail fasilitas untuk admin",
)
def get_hospital(
    hospital_id: str,
    connection: DbConnection,
    principal: HospitalEditor,
) -> dict[str, Any]:
    return _load_hospital(connection, hospital_id, principal)


@router.patch(
    "/hospitals/{hospital_id}",
    response_model=HospitalAdmin,
    summary="Memperbarui fasilitas; data terbit kembali menjadi draft",
)
def update_hospital(
    hospital_id: str,
    payload: HospitalUpdate,
    connection: DbConnection,
    principal: HospitalEditor,
) -> dict[str, Any]:
    _load_hospital(connection, hospital_id, principal)
    fields = payload.model_dump(exclude_unset=True)
    _normalise_update(fields, reset_published=True)
    row = catalog.update_hospital(
        connection, hospital_id, fields, now=utc_now().isoformat()
    )
    if row is None:
        raise not_found("Fasilitas tidak ditemukan.")
    _record(
        connection,
        principal,
        "update",
        "hospital",
        hospital_id,
        detail="Kolom: " + ", ".join(sorted(fields)),
    )
    return row


@router.post(
    "/hospitals/{hospital_id}/publish",
    response_model=HospitalAdmin,
    summary="Menerbitkan fasilitas yang telah terverifikasi",
)
def publish_hospital(
    hospital_id: str,
    connection: DbConnection,
    principal: HospitalEditor,
    settings: AppSettings,
) -> dict[str, Any]:
    row = _load_hospital(connection, hospital_id, principal)
    if row["status"] == PublicationStatus.PUBLISHED.value:
        return row
    ensure_hospital_publishable(row, production=settings.is_production)
    updated = catalog.update_hospital(
        connection,
        hospital_id,
        {"status": PublicationStatus.PUBLISHED.value},
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Fasilitas tidak ditemukan.")
    _record(connection, principal, "publish", "hospital", hospital_id)
    return updated


@router.post(
    "/hospitals/{hospital_id}/archive",
    response_model=HospitalAdmin,
    summary="Mengarsipkan fasilitas",
)
def archive_hospital(
    hospital_id: str,
    payload: StatusChangeRequest,
    connection: DbConnection,
    principal: HospitalEditor,
) -> dict[str, Any]:
    row = _load_hospital(connection, hospital_id, principal)
    if row["status"] == PublicationStatus.ARCHIVED.value:
        return row
    updated = catalog.update_hospital(
        connection,
        hospital_id,
        {"status": PublicationStatus.ARCHIVED.value},
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Fasilitas tidak ditemukan.")
    _record(
        connection,
        principal,
        "archive",
        "hospital",
        hospital_id,
        detail=payload.reason,
    )
    return updated


@router.post(
    "/hospitals/{hospital_id}/services",
    response_model=ServiceAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Membuat layanan (selalu draft)",
)
def create_service(
    hospital_id: str,
    payload: ServiceCreate,
    connection: DbConnection,
    principal: HospitalEditor,
) -> dict[str, Any]:
    _load_hospital(connection, hospital_id, principal)
    data = payload.model_dump()
    data["verified_at"] = to_iso(payload.verified_at)
    data["is_synthetic"] = int(payload.is_synthetic)
    row = catalog.create_service(
        connection,
        service_id=str(uuid.uuid4()),
        hospital_id=hospital_id,
        data=data,
        now=utc_now().isoformat(),
    )
    _record(connection, principal, "create", "hospital_service", row["id"])
    return row


@router.get(
    "/hospitals/{hospital_id}/services",
    response_model=Page[ServiceAdmin],
    summary="Daftar layanan untuk admin",
)
def list_services(
    hospital_id: str,
    connection: DbConnection,
    principal: HospitalEditor,
    status_filter: Annotated[PublicationStatus | None, Query(alias="status")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    _load_hospital(connection, hospital_id, principal)
    rows, total = catalog.list_services(
        connection,
        hospital_id,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.patch(
    "/services/{service_id}",
    response_model=ServiceAdmin,
    summary="Memperbarui layanan; data terbit kembali menjadi draft",
)
def update_service(
    service_id: str,
    payload: ServiceUpdate,
    connection: DbConnection,
    principal: HospitalEditor,
) -> dict[str, Any]:
    _load_service(connection, service_id, principal)
    fields = payload.model_dump(exclude_unset=True)
    _normalise_update(fields, reset_published=True)
    row = catalog.update_service(
        connection, service_id, fields, now=utc_now().isoformat()
    )
    if row is None:
        raise not_found("Layanan tidak ditemukan.")
    _record(
        connection,
        principal,
        "update",
        "hospital_service",
        service_id,
        detail="Kolom: " + ", ".join(sorted(fields)),
    )
    return row


@router.post(
    "/services/{service_id}/publish",
    response_model=ServiceAdmin,
    summary="Menerbitkan layanan yang telah terverifikasi",
)
def publish_service(
    service_id: str,
    connection: DbConnection,
    principal: HospitalEditor,
    settings: AppSettings,
) -> dict[str, Any]:
    row = _load_service(connection, service_id, principal)
    if row["status"] == PublicationStatus.PUBLISHED.value:
        return row
    ensure_service_publishable(row, production=settings.is_production)
    updated = catalog.update_service(
        connection,
        service_id,
        {"status": PublicationStatus.PUBLISHED.value},
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Layanan tidak ditemukan.")
    _record(connection, principal, "publish", "hospital_service", service_id)
    return updated


@router.post(
    "/services/{service_id}/archive",
    response_model=ServiceAdmin,
    summary="Mengarsipkan layanan",
)
def archive_service(
    service_id: str,
    payload: StatusChangeRequest,
    connection: DbConnection,
    principal: HospitalEditor,
) -> dict[str, Any]:
    row = _load_service(connection, service_id, principal)
    if row["status"] == PublicationStatus.ARCHIVED.value:
        return row
    updated = catalog.update_service(
        connection,
        service_id,
        {"status": PublicationStatus.ARCHIVED.value},
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Layanan tidak ditemukan.")
    _record(
        connection,
        principal,
        "archive",
        "hospital_service",
        service_id,
        detail=payload.reason,
    )
    return updated


@router.post(
    "/hospitals/{hospital_id}/visit-requirements",
    response_model=VisitRequirementAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Membuat persiapan kunjungan (selalu draft)",
)
def create_visit_requirement(
    hospital_id: str,
    payload: VisitRequirementCreate,
    connection: DbConnection,
    principal: HospitalEditor,
) -> dict[str, Any]:
    _load_hospital(connection, hospital_id, principal)
    data = payload.model_dump()
    data["verified_at"] = to_iso(payload.verified_at)
    data["is_synthetic"] = int(payload.is_synthetic)
    row = catalog.create_visit_requirement(
        connection,
        requirement_id=str(uuid.uuid4()),
        hospital_id=hospital_id,
        data=data,
        now=utc_now().isoformat(),
    )
    _record(connection, principal, "create", "visit_requirement", row["id"])
    return row


@router.get(
    "/hospitals/{hospital_id}/visit-requirements",
    response_model=Page[VisitRequirementAdmin],
    summary="Daftar persiapan kunjungan untuk admin",
)
def list_visit_requirements(
    hospital_id: str,
    connection: DbConnection,
    principal: HospitalEditor,
    status_filter: Annotated[PublicationStatus | None, Query(alias="status")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    _load_hospital(connection, hospital_id, principal)
    rows, total = catalog.list_visit_requirements(
        connection,
        hospital_id,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.patch(
    "/visit-requirements/{requirement_id}",
    response_model=VisitRequirementAdmin,
    summary="Memperbarui persiapan kunjungan; data terbit menjadi draft",
)
def update_visit_requirement(
    requirement_id: str,
    payload: VisitRequirementUpdate,
    connection: DbConnection,
    principal: HospitalEditor,
) -> dict[str, Any]:
    _load_requirement(connection, requirement_id, principal)
    fields = payload.model_dump(exclude_unset=True)
    _normalise_update(fields, reset_published=True)
    row = catalog.update_visit_requirement(
        connection, requirement_id, fields, now=utc_now().isoformat()
    )
    if row is None:
        raise not_found("Persiapan kunjungan tidak ditemukan.")
    _record(
        connection,
        principal,
        "update",
        "visit_requirement",
        requirement_id,
        detail="Kolom: " + ", ".join(sorted(fields)),
    )
    return row


@router.post(
    "/visit-requirements/{requirement_id}/publish",
    response_model=VisitRequirementAdmin,
    summary="Menerbitkan persiapan kunjungan terverifikasi",
)
def publish_visit_requirement(
    requirement_id: str,
    connection: DbConnection,
    principal: HospitalEditor,
    settings: AppSettings,
) -> dict[str, Any]:
    row = _load_requirement(connection, requirement_id, principal)
    if row["status"] == PublicationStatus.PUBLISHED.value:
        return row
    ensure_visit_requirement_publishable(row, production=settings.is_production)
    updated = catalog.update_visit_requirement(
        connection,
        requirement_id,
        {"status": PublicationStatus.PUBLISHED.value},
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Persiapan kunjungan tidak ditemukan.")
    _record(connection, principal, "publish", "visit_requirement", requirement_id)
    return updated


@router.post(
    "/visit-requirements/{requirement_id}/archive",
    response_model=VisitRequirementAdmin,
    summary="Mengarsipkan persiapan kunjungan",
)
def archive_visit_requirement(
    requirement_id: str,
    payload: StatusChangeRequest,
    connection: DbConnection,
    principal: HospitalEditor,
) -> dict[str, Any]:
    row = _load_requirement(connection, requirement_id, principal)
    if row["status"] == PublicationStatus.ARCHIVED.value:
        return row
    updated = catalog.update_visit_requirement(
        connection,
        requirement_id,
        {"status": PublicationStatus.ARCHIVED.value},
        now=utc_now().isoformat(),
    )
    if updated is None:
        raise not_found("Persiapan kunjungan tidak ditemukan.")
    _record(
        connection,
        principal,
        "archive",
        "visit_requirement",
        requirement_id,
        detail=payload.reason,
    )
    return updated
