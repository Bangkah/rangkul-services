from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import AdminCredential, Role
from app.errors import AppError, ErrorCode

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="AdminBearer",
    description="Token admin individual (header Authorization: Bearer <token>).",
)


@dataclass(frozen=True, slots=True)
class Principal:
    name: str
    role: Role
    hospital_id: str | None = None


def _unauthorized() -> AppError:
    return AppError(
        ErrorCode.UNAUTHORIZED,
        "Token akses admin tidak valid atau tidak tersedia.",
        401,
        {"WWW-Authenticate": "Bearer"},
    )


def get_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    token = credentials.credentials
    admin_credentials: tuple[AdminCredential, ...] = (
        request.app.state.settings.admin_credentials
    )
    matched: AdminCredential | None = None
    for credential in admin_credentials:
        if secrets.compare_digest(token, credential.token):
            matched = credential
    if matched is None:
        raise _unauthorized()
    return Principal(
        name=matched.name,
        role=matched.role,
        hospital_id=matched.hospital_id,
    )


def require_roles(*allowed: Role) -> Callable[..., Principal]:
    def dependency(
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> Principal:
        if principal.role not in allowed:
            raise AppError(
                ErrorCode.FORBIDDEN,
                "Peran admin tidak memiliki izin untuk tindakan ini.",
                403,
            )
        return principal

    return dependency


def ensure_hospital_scope(principal: Principal, hospital_id: str) -> None:
    if principal.role is Role.SYSTEM_ADMIN:
        return
    if principal.role is Role.HOSPITAL_ADMIN and principal.hospital_id == hospital_id:
        return
    raise AppError(
        ErrorCode.FORBIDDEN,
        "Admin tidak memiliki kewenangan atas fasilitas tersebut.",
        403,
    )
