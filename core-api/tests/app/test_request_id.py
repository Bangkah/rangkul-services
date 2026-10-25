from __future__ import annotations

import uuid


def test_valid_client_request_id_is_propagated(client):
    response = client.get(
        "/api/v1/health/live", headers={"X-Request-ID": "trace-abc-12345"}
    )

    assert response.headers["X-Request-ID"] == "trace-abc-12345"


def test_unsafe_client_request_id_is_replaced(client):
    response = client.get(
        "/api/v1/health/live", headers={"X-Request-ID": "pendek <script>"}
    )

    request_id = response.headers["X-Request-ID"]
    assert request_id != "pendek <script>"
    uuid.UUID(request_id)


def test_error_body_carries_same_request_id(client):
    response = client.get(
        "/api/v1/tidak-ada", headers={"X-Request-ID": "trace-error-12345"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["request_id"] == "trace-error-12345"
    assert response.headers["X-Request-ID"] == "trace-error-12345"
