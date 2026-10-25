from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Role
from app.errors import ErrorResponse
from app.security import Principal, get_principal

router = APIRouter(prefix="/admin", tags=["Administrasi"])


class AdminIdentity(BaseModel):
    name: str
    role: Role
    hospital_id: str | None


@router.get(
    "/me",
    response_model=AdminIdentity,
    summary="Identitas admin pemanggil",
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Token tidak valid atau tidak tersedia",
        },
        403: {"model": ErrorResponse, "description": "Tidak diizinkan"},
    },
)
def me(
    principal: Annotated[Principal, Depends(get_principal)],
) -> AdminIdentity:
    return AdminIdentity(
        name=principal.name,
        role=principal.role,
        hospital_id=principal.hospital_id,
    )
