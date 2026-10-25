from __future__ import annotations

import pytest

from app.config import Role
from app.errors import AppError, ErrorCode
from app.security import Principal, ensure_hospital_scope, require_roles

SYSTEM_TOKEN = "system-admin-token-0123456789abcdef"
REVIEWER_TOKEN = "content-reviewer-token-0123456789"
HOSPITAL_TOKEN = "hospital-admin-token-0123456789"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_missing_token_is_rejected(client):
    response = client.get("/api/v1/admin/me")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_unknown_token_is_rejected(client):
    response = client.get("/api/v1/admin/me", headers=_auth("token-palsu"))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert "token-palsu" not in response.text


def test_system_admin_identity(client):
    response = client.get("/api/v1/admin/me", headers=_auth(SYSTEM_TOKEN))

    assert response.status_code == 200
    assert response.json() == {
        "name": "Admin Sistem",
        "role": "system_admin",
        "hospital_id": None,
    }


def test_hospital_admin_identity_keeps_scope(client):
    response = client.get("/api/v1/admin/me", headers=_auth(HOSPITAL_TOKEN))

    assert response.status_code == 200
    assert response.json() == {
        "name": "Admin RS A",
        "role": "hospital_admin",
        "hospital_id": "rs-a",
    }


def test_content_reviewer_can_authenticate(client):
    response = client.get("/api/v1/admin/me", headers=_auth(REVIEWER_TOKEN))

    assert response.status_code == 200
    assert response.json()["role"] == "content_reviewer"


def test_require_roles_allows_and_forbids():
    dependency = require_roles(Role.CONTENT_REVIEWER)
    reviewer = Principal(name="Reviewer", role=Role.CONTENT_REVIEWER)
    hospital_admin = Principal(
        name="Admin RS", role=Role.HOSPITAL_ADMIN, hospital_id="rs-a"
    )

    assert dependency(reviewer) is reviewer
    with pytest.raises(AppError) as excinfo:
        dependency(hospital_admin)
    assert excinfo.value.code is ErrorCode.FORBIDDEN
    assert excinfo.value.status_code == 403


def test_hospital_scope_rules():
    system_admin = Principal(name="Sistem", role=Role.SYSTEM_ADMIN)
    hospital_admin = Principal(
        name="Admin RS A", role=Role.HOSPITAL_ADMIN, hospital_id="rs-a"
    )
    reviewer = Principal(name="Reviewer", role=Role.CONTENT_REVIEWER)

    ensure_hospital_scope(system_admin, "rs-b")
    ensure_hospital_scope(hospital_admin, "rs-a")

    for principal in (hospital_admin, reviewer):
        with pytest.raises(AppError) as excinfo:
            ensure_hospital_scope(principal, "rs-b")
        assert excinfo.value.code is ErrorCode.FORBIDDEN


def test_admin_endpoints_are_documented_with_bearer_security(client):
    schema = client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["AdminBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/api/v1/admin/me"]["get"]["security"] == [
        {"AdminBearer": []}
    ]
