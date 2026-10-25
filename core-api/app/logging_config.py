from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_EXTRA_FIELDS = (
    "method",
    "path",
    "status_code",
    "duration_ms",
    "applied_migrations",
    "app_env",
    "version",
    "reason",
)
_LOGGER_NAME = "app"
_HANDLER_MARKER = "_rangkul_json_handler"


class JsonFormatter(logging.Formatter):
    """Formatter JSON tanpa isi permintaan; hanya metadata teknis."""

    def format(self, record: logging.LogRecord) -> str:
        record_request_id = getattr(record, "request_id", None)
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": record_request_id or request_id_var.get(),
        }
        for name in _EXTRA_FIELDS:
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, _HANDLER_MARKER, True)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
