from __future__ import annotations


def test_openapi_contains_phase_contract(client):
    schema = client.get("/openapi.json").json()

    paths = schema["paths"]
    required = {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/admin/me",
        "/api/v1/hospitals",
        "/api/v1/hospitals/{hospital_id}",
        "/api/v1/hospitals/{hospital_id}/services",
        "/api/v1/hospitals/{hospital_id}/visit-requirements",
        "/api/v1/articles",
        "/api/v1/articles/{article_id}",
        "/api/v1/chat",
        "/api/v1/chat/stream",
        "/api/v1/admin/hospitals",
        "/api/v1/admin/hospitals/{hospital_id}",
        "/api/v1/admin/hospitals/{hospital_id}/publish",
        "/api/v1/admin/hospitals/{hospital_id}/archive",
        "/api/v1/admin/services/{service_id}",
        "/api/v1/admin/services/{service_id}/publish",
        "/api/v1/admin/services/{service_id}/archive",
        "/api/v1/admin/visit-requirements/{requirement_id}",
        "/api/v1/admin/visit-requirements/{requirement_id}/publish",
        "/api/v1/admin/visit-requirements/{requirement_id}/archive",
        "/api/v1/admin/knowledge-documents",
        "/api/v1/admin/knowledge-documents/{record_id}",
        "/api/v1/admin/knowledge-documents/{record_id}/submit-review",
        "/api/v1/admin/knowledge-documents/{record_id}/review",
        "/api/v1/admin/knowledge-documents/{record_id}/publish",
        "/api/v1/admin/knowledge-documents/{record_id}/archive",
        "/api/v1/admin/knowledge-documents/{record_id}/revoke",
        "/api/v1/admin/articles",
        "/api/v1/admin/articles/{article_id}",
        "/api/v1/admin/articles/{article_id}/publish",
        "/api/v1/admin/articles/{article_id}/archive",
        "/api/v1/admin/audit-events",
    }
    assert required <= set(paths)
    assert schema["info"]["version"] == "0.3.0"
    assert "ErrorResponse" in schema["components"]["schemas"]


def test_openapi_request_id_header_is_not_required(client):
    schema = client.get("/openapi.json").json()

    live = schema["paths"]["/api/v1/health/live"]["get"]
    assert live["responses"]["200"]["content"]["application/json"]
