from __future__ import annotations

import json
import logging

from app.logging_config import JsonFormatter, configure_logging, request_id_var


def _record(message: str = "pesan uji") -> logging.LogRecord:
    return logging.LogRecord("app", logging.INFO, __file__, 1, message, (), None)


def test_formatter_emits_json_with_context_request_id():
    token = request_id_var.set("req-12345678")
    try:
        payload = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app"
    assert payload["message"] == "pesan uji"
    assert payload["request_id"] == "req-12345678"


def test_formatter_includes_only_safe_extra_fields():
    record = _record()
    record.method = "GET"
    record.path = "/api/v1/health/live"
    record.status_code = 200
    record.duration_ms = 1.5
    record.request_id = "req-extra-1234"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/health/live"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 1.5
    assert payload["request_id"] == "req-extra-1234"


def test_formatter_drops_unexpected_extra_fields():
    record = _record()
    record.token = "rahasia-tidak-boleh-muncul"
    record.chat = "isi percakapan"

    rendered = JsonFormatter().format(record)

    assert "rahasia-tidak-boleh-muncul" not in rendered
    assert "isi percakapan" not in rendered


def test_formatter_keeps_exception_for_server_logs():
    record = _record()
    try:
        raise ValueError("contoh kesalahan")
    except ValueError:
        import sys

        record.exc_info = sys.exc_info()

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: contoh kesalahan" in payload["exception"]


def test_configure_logging_replaces_its_own_handler_only():
    configure_logging("INFO")
    configure_logging("WARNING")
    handlers = [
        handler
        for handler in logging.getLogger("app").handlers
        if getattr(handler, "_rangkul_json_handler", False)
    ]

    assert len(handlers) == 1
    assert logging.getLogger("app").level == logging.WARNING
