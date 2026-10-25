from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(admin.router)
