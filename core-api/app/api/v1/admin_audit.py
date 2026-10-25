from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app import audit
from app.api.deps import DbConnection
from app.config import Role
from app.schemas import AuditEvent, Page
from app.security import Principal, require_roles

router = APIRouter(prefix="/admin", tags=["Admin - Audit"])

SystemAdmin = Annotated[Principal, Depends(require_roles(Role.SYSTEM_ADMIN))]

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get(
    "/audit-events",
    response_model=Page[AuditEvent],
    summary="Menelusuri tindakan administratif",
)
def list_audit_events(
    connection: DbConnection,
    principal: SystemAdmin,
    object_type: str | None = None,
    object_id: str | None = None,
    action: str | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    rows, total = audit.list_events(
        connection,
        object_type=object_type,
        object_id=object_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}
