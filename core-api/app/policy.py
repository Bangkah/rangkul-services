from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.errors import AppError, ErrorCode
from app.schemas import KnowledgeStatus, PublicationStatus

UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(value: datetime | None) -> str | None:
    """Normalisasi waktu ke RFC 3339 UTC; waktu tanpa zona waktu ditolak."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Waktu harus menyertakan zona waktu eksplisit.",
            422,
        )
    return value.astimezone(UTC).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def is_expired(review_due_at: str | None, *, now: datetime | None = None) -> bool:
    due = parse_iso(review_due_at)
    if due is None:
        return False
    return due <= (now or utc_now())


def directions_url(latitude: float | None, longitude: float | None) -> str | None:
    if latitude is None or longitude is None:
        return None
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&destination={latitude:.6f},{longitude:.6f}"
    )


def invalid(message: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, message, 422)


def conflict(message: str) -> AppError:
    return AppError(ErrorCode.CONFLICT, message, 409)


def not_found(message: str) -> AppError:
    return AppError(ErrorCode.NOT_FOUND, message, 404)


def _missing(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return any(row.get(field) in (None, "") for field in fields)


def ensure_synthetic_allowed(is_synthetic: bool, *, production: bool) -> None:
    if is_synthetic and production:
        raise invalid(
            "Data sintetis tidak boleh dipublikasikan di lingkungan produksi."
        )


def ensure_hospital_publishable(row: Mapping[str, Any], *, production: bool) -> None:
    if _missing(row, ("name", "address", "source", "verified_at")):
        raise invalid(
            "Fasilitas memerlukan nama, alamat, sumber, dan tanggal verifikasi "
            "sebelum dipublikasikan."
        )
    if row.get("latitude") is None or row.get("longitude") is None:
        raise invalid("Koordinat fasilitas wajib diisi sebelum dipublikasikan.")
    ensure_synthetic_allowed(bool(row.get("is_synthetic")), production=production)


def ensure_service_publishable(row: Mapping[str, Any], *, production: bool) -> None:
    if _missing(row, ("name", "source", "verified_at")):
        raise invalid(
            "Layanan memerlukan nama, sumber, dan tanggal verifikasi sebelum "
            "dipublikasikan."
        )
    ensure_synthetic_allowed(bool(row.get("is_synthetic")), production=production)


def ensure_visit_requirement_publishable(
    row: Mapping[str, Any], *, production: bool
) -> None:
    if _missing(row, ("title", "source", "verified_at")):
        raise invalid(
            "Persiapan kunjungan memerlukan judul, sumber, dan tanggal verifikasi "
            "sebelum dipublikasikan."
        )
    ensure_synthetic_allowed(bool(row.get("is_synthetic")), production=production)


def ensure_article_publishable(row: Mapping[str, Any], *, production: bool) -> None:
    if _missing(row, ("title", "content", "source")):
        raise invalid(
            "Artikel memerlukan judul, isi, dan sumber sebelum dipublikasikan."
        )
    ensure_synthetic_allowed(bool(row.get("is_synthetic")), production=production)


def ensure_knowledge_publishable(row: Mapping[str, Any], *, production: bool) -> None:
    if row.get("status") != KnowledgeStatus.APPROVED.value:
        raise conflict("Dokumen harus disetujui peninjau sebelum diterbitkan.")
    if _missing(row, ("title", "source", "owner", "content", "reviewed_at")):
        raise invalid(
            "Dokumen pengetahuan memerlukan judul, sumber, pemilik, isi, dan "
            "bukti peninjauan sebelum diterbitkan."
        )
    if is_expired(row.get("review_due_at")):
        raise invalid(
            "Dokumen sudah melewati masa peninjauan dan tidak dapat diterbitkan."
        )
    ensure_synthetic_allowed(bool(row.get("is_synthetic")), production=production)


def publication_is_visible(
    status: str, verified_at: str | None, review_due_at: str | None = None
) -> bool:
    if status != PublicationStatus.PUBLISHED.value:
        return False
    if not verified_at:
        return False
    return not is_expired(review_due_at)
