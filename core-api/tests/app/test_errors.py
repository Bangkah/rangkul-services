from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app


def _app_with_probe_routes(settings):
    app = create_app(settings)

    @app.get("/api/v1/probe/boom")
    def boom() -> None:
        raise RuntimeError("rahasia internal tidak boleh bocor")

    @app.get("/api/v1/probe/validate")
    def validate(count: int) -> dict[str, int]:
        return {"count": count}

    @app.get("/api/v1/probe/status-tak-dikenal")
    def unknown_status() -> None:
        raise HTTPException(status_code=418, detail="detail internal")

    return app


def test_unknown_path_uses_error_envelope(client):
    response = client.get("/api/v1/tidak-ada")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_method_not_allowed_uses_error_envelope(client):
    response = client.post("/api/v1/health/live")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_unmapped_status_code_uses_generic_error(settings):
    with TestClient(_app_with_probe_routes(settings)) as client:
        response = client.get("/api/v1/probe/status-tak-dikenal")

    assert response.status_code == 418
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "detail internal" not in response.text


def test_validation_error_hides_internal_details(settings):
    with TestClient(_app_with_probe_routes(settings)) as client:
        response = client.get("/api/v1/probe/validate", params={"count": "bukan-angka"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Permintaan tidak valid."
    assert "bukan-angka" not in response.text
    assert "traceback" not in response.text.lower()


def test_unexpected_exception_returns_safe_500(settings):
    with TestClient(_app_with_probe_routes(settings)) as client:
        response = client.get("/api/v1/probe/boom")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert "rahasia internal" not in response.text
    assert "RuntimeError" not in response.text
    assert "traceback" not in response.text.lower()


def test_cors_and_exposed_request_id(client):
    response = client.get(
        "/api/v1/health/live", headers={"Origin": "http://localhost:3000"}
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]
