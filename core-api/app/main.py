from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import Settings
from app.db import Database
from app.errors import install_exception_handlers
from app.logging_config import configure_logging
from app.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.providers import FakeLLMProvider

logger = logging.getLogger("app.startup")

APP_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    configure_logging(resolved.log_level)
    database = Database(resolved.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        applied = database.migrate()
        logger.info(
            "startup_complete",
            extra={"app_env": resolved.app_env, "applied_migrations": applied},
        )
        yield

    app = FastAPI(
        title="RANGKUL Core API",
        description=(
            "Fondasi backend RANGKUL AI sesuai SRS. Fase 0 mencakup kontrak "
            "API berversi, model error konsisten, request ID, logging aman, "
            "database dan migrasi, otorisasi admin minimum, serta health check."
        ),
        version=APP_VERSION,
        lifespan=lifespan,
    )

    app.state.settings = resolved
    app.state.db = database
    app.state.llm = FakeLLMProvider()

    app.add_middleware(
        RequestContextMiddleware,
        header_name=REQUEST_ID_HEADER,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )

    install_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
