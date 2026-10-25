from __future__ import annotations

from tests.app.test_public_catalog import (
    VERIFIED_AT,
    article_payload,
    create_hospital,
    hospital_payload,
    publish,
    requirement_payload,
    service_payload,
)


def test_admin_catalog_requires_authentication_and_role(client, reviewer_auth):
    assert client.get("/api/v1/admin/hospitals").status_code == 401
    assert (
        client.get("/api/v1/admin/hospitals", headers=reviewer_auth).status_code == 403
    )
    assert (
        client.get("/api/v1/admin/hospitals/rs-a", headers=reviewer_auth).status_code
        == 403
    )


def test_create_hospital_is_draft_and_duplicate_conflicts(client, system_auth):
    created = create_hospital(client, system_auth)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["is_synthetic"] is False
    assert body["verified_at"].startswith("2026-01-01T00:00:00")

    duplicate = create_hospital(client, system_auth)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"

    listed = client.get(
        "/api/v1/admin/hospitals", headers=system_auth, params={"status": "draft"}
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_hospital_publish_validation_and_success(client, system_auth):
    created = client.post(
        "/api/v1/admin/hospitals",
        headers=system_auth,
        json={"id": "rs-min", "name": "RS Minimal"},
    )
    assert created.status_code == 201
    invalid = publish(client, system_auth, "/api/v1/admin/hospitals/rs-min/publish")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    patched = client.patch(
        "/api/v1/admin/hospitals/rs-min",
        headers=system_auth,
        json={
            "address": "Jl. Uji",
            "latitude": -6.2,
            "longitude": 106.8,
            "source": "Sumber uji",
            "verified_at": VERIFIED_AT,
        },
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "draft"

    published = publish(client, system_auth, "/api/v1/admin/hospitals/rs-min/publish")
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    again = publish(client, system_auth, "/api/v1/admin/hospitals/rs-min/publish")
    assert again.status_code == 200
    assert client.get("/api/v1/hospitals/rs-min").status_code == 200


def test_edit_published_hospital_returns_to_draft(client, system_auth):
    assert create_hospital(client, system_auth).status_code == 201
    assert (
        publish(client, system_auth, "/api/v1/admin/hospitals/rs-a/publish").status_code
        == 200
    )

    edited = client.patch(
        "/api/v1/admin/hospitals/rs-a",
        headers=system_auth,
        json={"name": "RS A Diperbarui"},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "draft"
    assert edited.json()["verified_at"] is None
    assert client.get("/api/v1/hospitals/rs-a").status_code == 404


def test_hospital_admin_scope_is_enforced(client, system_auth, hospital_auth):
    assert create_hospital(client, system_auth, "rs-a").status_code == 201
    assert create_hospital(client, system_auth, "rs-b").status_code == 201

    own = client.get("/api/v1/admin/hospitals/rs-a", headers=hospital_auth)
    assert own.status_code == 200
    other = client.get("/api/v1/admin/hospitals/rs-b", headers=hospital_auth)
    assert other.status_code == 403

    listed = client.get("/api/v1/admin/hospitals", headers=hospital_auth)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == ["rs-a"]

    forbidden_create = client.post(
        "/api/v1/admin/hospitals/rs-b/services",
        headers=hospital_auth,
        json=service_payload(),
    )
    assert forbidden_create.status_code == 403

    service = client.post(
        "/api/v1/admin/hospitals/rs-a/services",
        headers=hospital_auth,
        json=service_payload(),
    )
    assert service.status_code == 201

    other_service = client.post(
        "/api/v1/admin/hospitals/rs-b/services",
        headers=system_auth,
        json=service_payload(),
    )
    assert other_service.status_code == 201
    denied_update = client.patch(
        f"/api/v1/admin/services/{other_service.json()['id']}",
        headers=hospital_auth,
        json={"name": "Tidak boleh"},
    )
    assert denied_update.status_code == 403

    other_requirement = client.post(
        "/api/v1/admin/hospitals/rs-b/visit-requirements",
        headers=system_auth,
        json=requirement_payload(),
    )
    assert other_requirement.status_code == 201
    denied_requirement = client.patch(
        f"/api/v1/admin/visit-requirements/{other_requirement.json()['id']}",
        headers=hospital_auth,
        json={"title": "Tidak boleh"},
    )
    assert denied_requirement.status_code == 403


def test_service_lifecycle(client, system_auth):
    assert create_hospital(client, system_auth).status_code == 201
    assert (
        publish(client, system_auth, "/api/v1/admin/hospitals/rs-a/publish").status_code
        == 200
    )
    created = client.post(
        "/api/v1/admin/hospitals/rs-a/services",
        headers=system_auth,
        json={"name": "Layanan tanpa sumber"},
    )
    assert created.status_code == 201
    service_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    invalid = publish(
        client, system_auth, f"/api/v1/admin/services/{service_id}/publish"
    )
    assert invalid.status_code == 422

    patched = client.patch(
        f"/api/v1/admin/services/{service_id}",
        headers=system_auth,
        json={"source": "Sumber uji", "verified_at": VERIFIED_AT},
    )
    assert patched.status_code == 200
    assert (
        publish(
            client, system_auth, f"/api/v1/admin/services/{service_id}/publish"
        ).status_code
        == 200
    )
    assert client.get("/api/v1/hospitals/rs-a/services").json()["total"] == 1

    edited = client.patch(
        f"/api/v1/admin/services/{service_id}",
        headers=system_auth,
        json={"description": "Diperbarui"},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "draft"
    assert client.get("/api/v1/hospitals/rs-a/services").json()["total"] == 0

    archived = client.post(
        f"/api/v1/admin/services/{service_id}/archive",
        headers=system_auth,
        json={"reason": "Uji arsip"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    again = client.post(
        f"/api/v1/admin/services/{service_id}/archive",
        headers=system_auth,
        json={"reason": "Uji arsip ulang"},
    )
    assert again.status_code == 200


def test_visit_requirement_lifecycle_and_ordering(client, system_auth):
    assert create_hospital(client, system_auth).status_code == 201
    assert (
        publish(client, system_auth, "/api/v1/admin/hospitals/rs-a/publish").status_code
        == 200
    )
    second = client.post(
        "/api/v1/admin/hospitals/rs-a/visit-requirements",
        headers=system_auth,
        json=requirement_payload(title="Kedua", sort_order=2),
    )
    first = client.post(
        "/api/v1/admin/hospitals/rs-a/visit-requirements",
        headers=system_auth,
        json=requirement_payload(title="Pertama", sort_order=1),
    )
    assert second.status_code == 201
    assert first.status_code == 201
    assert (
        publish(
            client,
            system_auth,
            f"/api/v1/admin/visit-requirements/{second.json()['id']}/publish",
        ).status_code
        == 200
    )
    assert (
        publish(
            client,
            system_auth,
            f"/api/v1/admin/visit-requirements/{first.json()['id']}/publish",
        ).status_code
        == 200
    )

    public = client.get("/api/v1/hospitals/rs-a/visit-requirements").json()
    assert [item["title"] for item in public["items"]] == ["Pertama", "Kedua"]

    edited = client.patch(
        f"/api/v1/admin/visit-requirements/{first.json()['id']}",
        headers=system_auth,
        json={"title": "Pertama diperbarui"},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "draft"
    assert client.get("/api/v1/hospitals/rs-a/visit-requirements").json()["total"] == 1

    archived = client.post(
        f"/api/v1/admin/visit-requirements/{second.json()['id']}/archive",
        headers=system_auth,
        json={"reason": "Uji arsip"},
    )
    assert archived.status_code == 200
    assert client.get("/api/v1/hospitals/rs-a/visit-requirements").json()["total"] == 0


def test_admin_service_and_requirement_lists(client, system_auth):
    assert create_hospital(client, system_auth).status_code == 201
    draft_service = client.post(
        "/api/v1/admin/hospitals/rs-a/services",
        headers=system_auth,
        json=service_payload(name="Draf"),
    )
    published_service = client.post(
        "/api/v1/admin/hospitals/rs-a/services",
        headers=system_auth,
        json=service_payload(name="Terbit"),
    )
    assert draft_service.status_code == 201
    assert published_service.status_code == 201
    assert (
        publish(
            client,
            system_auth,
            f"/api/v1/admin/services/{published_service.json()['id']}/publish",
        ).status_code
        == 200
    )
    again = publish(
        client,
        system_auth,
        f"/api/v1/admin/services/{published_service.json()['id']}/publish",
    )
    assert again.status_code == 200

    drafts = client.get(
        "/api/v1/admin/hospitals/rs-a/services",
        headers=system_auth,
        params={"status": "draft"},
    )
    assert drafts.status_code == 200
    assert drafts.json()["total"] == 1
    assert drafts.json()["items"][0]["id"] == draft_service.json()["id"]
    all_services = client.get(
        "/api/v1/admin/hospitals/rs-a/services", headers=system_auth
    )
    assert all_services.json()["total"] == 2

    draft_requirement = client.post(
        "/api/v1/admin/hospitals/rs-a/visit-requirements",
        headers=system_auth,
        json=requirement_payload(title="Draf"),
    )
    published_requirement = client.post(
        "/api/v1/admin/hospitals/rs-a/visit-requirements",
        headers=system_auth,
        json=requirement_payload(title="Terbit"),
    )
    assert draft_requirement.status_code == 201
    assert published_requirement.status_code == 201
    assert (
        publish(
            client,
            system_auth,
            f"/api/v1/admin/visit-requirements/"
            f"{published_requirement.json()['id']}/publish",
        ).status_code
        == 200
    )
    again_requirement = publish(
        client,
        system_auth,
        f"/api/v1/admin/visit-requirements/"
        f"{published_requirement.json()['id']}/publish",
    )
    assert again_requirement.status_code == 200

    requirements = client.get(
        "/api/v1/admin/hospitals/rs-a/visit-requirements",
        headers=system_auth,
        params={"status": "published"},
    )
    assert requirements.status_code == 200
    assert requirements.json()["total"] == 1
    assert (
        client.get(
            "/api/v1/admin/hospitals/rs-a/visit-requirements",
            headers=system_auth,
        ).json()["total"]
        == 2
    )

    assert (
        client.get(
            "/api/v1/admin/hospitals/tidak-ada/services", headers=system_auth
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/admin/hospitals/tidak-ada/visit-requirements",
            headers=system_auth,
        ).status_code
        == 404
    )


def test_publish_requires_coordinates_and_visit_source(client, system_auth):
    created = client.post(
        "/api/v1/admin/hospitals",
        headers=system_auth,
        json={
            "id": "rs-tanpa-koordinat",
            "name": "RS Tanpa Koordinat",
            "address": "Jl. Uji",
            "source": "Sumber uji",
            "verified_at": VERIFIED_AT,
        },
    )
    assert created.status_code == 201
    assert (
        publish(
            client,
            system_auth,
            "/api/v1/admin/hospitals/rs-tanpa-koordinat/publish",
        ).status_code
        == 422
    )

    assert create_hospital(client, system_auth, "rs-a").status_code == 201
    requirement = client.post(
        "/api/v1/admin/hospitals/rs-a/visit-requirements",
        headers=system_auth,
        json={"title": "Tanpa sumber"},
    )
    assert requirement.status_code == 201
    requirement_id = requirement.json()["id"]
    assert (
        publish(
            client,
            system_auth,
            f"/api/v1/admin/visit-requirements/{requirement_id}/publish",
        ).status_code
        == 422
    )
    patched = client.patch(
        f"/api/v1/admin/visit-requirements/{requirement_id}",
        headers=system_auth,
        json={"source": "Sumber uji", "verified_at": VERIFIED_AT},
    )
    assert patched.status_code == 200
    assert (
        publish(
            client,
            system_auth,
            f"/api/v1/admin/visit-requirements/{requirement_id}/publish",
        ).status_code
        == 200
    )


def test_unknown_ids_and_invalid_payloads(client, system_auth):
    assert (
        client.get("/api/v1/admin/hospitals/tidak-ada", headers=system_auth).status_code
        == 404
    )
    assert (
        client.patch(
            "/api/v1/admin/hospitals/tidak-ada",
            headers=system_auth,
            json={"name": "X"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/api/v1/admin/services/tidak-ada",
            headers=system_auth,
            json={"name": "X"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/api/v1/admin/visit-requirements/tidak-ada",
            headers=system_auth,
            json={"title": "X"},
        ).status_code
        == 404
    )

    assert create_hospital(client, system_auth).status_code == 201
    empty = client.patch("/api/v1/admin/hospitals/rs-a", headers=system_auth, json={})
    assert empty.status_code == 422
    unknown_field = client.patch(
        "/api/v1/admin/hospitals/rs-a",
        headers=system_auth,
        json={"nama": "Salah"},
    )
    assert unknown_field.status_code == 422
    naive_time = client.patch(
        "/api/v1/admin/hospitals/rs-a",
        headers=system_auth,
        json={"verified_at": "2026-01-01T00:00:00"},
    )
    assert naive_time.status_code == 422
    bad_status = client.get(
        "/api/v1/admin/hospitals",
        headers=system_auth,
        params={"status": "tidak-ada"},
    )
    assert bad_status.status_code == 422


def test_hospital_archive_is_idempotent_and_hides_public_data(client, system_auth):
    assert create_hospital(client, system_auth).status_code == 201
    assert (
        publish(client, system_auth, "/api/v1/admin/hospitals/rs-a/publish").status_code
        == 200
    )
    archived = client.post(
        "/api/v1/admin/hospitals/rs-a/archive",
        headers=system_auth,
        json={"reason": "Uji arsip"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert client.get("/api/v1/hospitals/rs-a").status_code == 404
    again = client.post(
        "/api/v1/admin/hospitals/rs-a/archive",
        headers=system_auth,
        json={"reason": "Uji arsip ulang"},
    )
    assert again.status_code == 200


def test_synthetic_hospital_cannot_be_published_in_production(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.app.conftest import build_settings

    settings = build_settings(tmp_path, app_env="production")
    with TestClient(create_app(settings)) as client:
        auth = {"Authorization": "Bearer system-admin-token-0123456789abcdef"}
        created = client.post(
            "/api/v1/admin/hospitals",
            headers=auth,
            json=hospital_payload("rs-sintetis", is_synthetic=True),
        )
        assert created.status_code == 201
        denied = client.post(
            "/api/v1/admin/hospitals/rs-sintetis/publish", headers=auth
        )
        assert denied.status_code == 422
        assert "sintetis" in denied.json()["error"]["message"]

        article = client.post(
            "/api/v1/admin/articles",
            headers=auth,
            json=article_payload(is_synthetic=True),
        )
        assert article.status_code == 201
        article_id = article.json()["id"]
        denied_article = client.post(
            f"/api/v1/admin/articles/{article_id}/publish", headers=auth
        )
        assert denied_article.status_code == 422
