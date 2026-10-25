from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    admin_articles,
    admin_audit,
    admin_hospitals,
    admin_knowledge,
    health,
    public,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(public.router)
api_router.include_router(admin.router)
api_router.include_router(admin_hospitals.router)
api_router.include_router(admin_knowledge.router)
api_router.include_router(admin_articles.router)
api_router.include_router(admin_audit.router)
