from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.db import Database


def get_connection(request: Request) -> Iterator[sqlite3.Connection]:
    database: Database = request.app.state.db
    with database.connect() as connection:
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


DbConnection = Annotated[sqlite3.Connection, Depends(get_connection)]
AppSettings = Annotated[Settings, Depends(get_settings)]
