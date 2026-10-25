from __future__ import annotations


def test_openapi_contains_phase_zero_contract(client):
    schema = client.get("/openapi.json").json()

    paths = schema["paths"]
    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths
    assert "/api/v1/admin/me" in paths
    assert schema["info"]["version"] == "0.1.0"
    assert "ErrorResponse" in schema["components"]["schemas"]


def test_openapi_request_id_header_is_not_required(client):
    schema = client.get("/openapi.json").json()

    live = schema["paths"]["/api/v1/health/live"]["get"]
    assert live["responses"]["200"]["content"]["application/json"]
