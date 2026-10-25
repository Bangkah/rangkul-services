from __future__ import annotations

from typing import Any

VERIFIED_AT = "2026-01-01T00:00:00+00:00"


def hospital_payload(hospital_id: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": hospital_id,
        "name": f"RS {hospital_id}",
        "address": "Jl. Uji No. 1",
        "latitude": 5.1801,
        "longitude": 97.1507,
        "contact_phone": "+62-000-0000",
        "contact_email": "uji@contoh.invalid",
        "operating_hours": "08.00-16.00",
        "source": "Sumber uji sintetis",
        "verified_at": VERIFIED_AT,
    }
    payload.update(overrides)
    return payload


def service_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Layanan uji",
        "description": "Deskripsi layanan uji.",
        "requirements": "Persyaratan uji.",
        "source": "Sumber uji sintetis",
        "verified_at": VERIFIED_AT,
    }
    payload.update(overrides)
    return payload


def requirement_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Persiapan uji",
        "description": "Deskripsi persiapan uji.",
        "sort_order": 1,
        "source": "Sumber uji sintetis",
        "verified_at": VERIFIED_AT,
    }
    payload.update(overrides)
    return payload


def article_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Artikel uji",
        "summary": "Ringkasan artikel uji.",
        "content": "Isi artikel uji.",
        "source": "Sumber uji sintetis",
    }
    payload.update(overrides)
    return payload


def create_hospital(client, auth, hospital_id: str = "rs-a", **overrides: Any):
    return client.post(
        "/api/v1/admin/hospitals",
        headers=auth,
        json=hospital_payload(hospital_id, **overrides),
    )


def publish(client, auth, path: str):
    return client.post(path, headers=auth)


def test_public_lists_only_published_content(client, system_auth):
    assert create_hospital(client, system_auth, "rs-pub").status_code == 201
    assert (
        publish(
            client, system_auth, "/api/v1/admin/hospitals/rs-pub/publish"
        ).status_code
        == 200
    )
    assert create_hospital(client, system_auth, "rs-draft").status_code == 201

    service = client.post(
        "/api/v1/admin/hospitals/rs-pub/services",
        headers=system_auth,
        json=service_payload(name="Layanan terbit"),
    )
    assert service.status_code == 201
    service_id = service.json()["id"]
    assert (
        publish(
            client, system_auth, f"/api/v1/admin/services/{service_id}/publish"
        ).status_code
        == 200
    )
    draft_service = client.post(
        "/api/v1/admin/hospitals/rs-pub/services",
        headers=system_auth,
        json=service_payload(name="Layanan draf"),
    )
    assert draft_service.status_code == 201

    requirement = client.post(
        "/api/v1/admin/hospitals/rs-pub/visit-requirements",
        headers=system_auth,
        json=requirement_payload(),
    )
    assert requirement.status_code == 201
    requirement_id = requirement.json()["id"]
    assert (
        publish(
            client,
            system_auth,
            f"/api/v1/admin/visit-requirements/{requirement_id}/publish",
        ).status_code
        == 200
    )
    draft_requirement = client.post(
        "/api/v1/admin/hospitals/rs-pub/visit-requirements",
        headers=system_auth,
        json=requirement_payload(title="Persiapan draf"),
    )
    assert draft_requirement.status_code == 201

    article = client.post(
        "/api/v1/admin/articles", headers=system_auth, json=article_payload()
    )
    assert article.status_code == 201
    article_id = article.json()["id"]
    assert (
        publish(
            client, system_auth, f"/api/v1/admin/articles/{article_id}/publish"
        ).status_code
        == 200
    )
    draft_article = client.post(
        "/api/v1/admin/articles",
        headers=system_auth,
        json=article_payload(title="Artikel draf"),
    )
    assert draft_article.status_code == 201

    hospitals = client.get("/api/v1/hospitals")
    assert hospitals.status_code == 200
    assert hospitals.json()["total"] == 1
    assert [item["id"] for item in hospitals.json()["items"]] == ["rs-pub"]
    hospital = hospitals.json()["items"][0]
    assert "status" not in hospital
    assert "created_at" not in hospital
    assert hospital["directions_url"].startswith(
        "https://www.google.com/maps/dir/?api=1"
    )
    assert "5.180100,97.150700" in hospital["directions_url"]

    assert client.get("/api/v1/hospitals/rs-pub").status_code == 200
    assert client.get("/api/v1/hospitals/rs-draft").status_code == 404

    services = client.get("/api/v1/hospitals/rs-pub/services")
    assert services.status_code == 200
    assert services.json()["total"] == 1
    assert services.json()["items"][0]["name"] == "Layanan terbit"
    assert "status" not in services.json()["items"][0]
    assert client.get("/api/v1/hospitals/rs-draft/services").status_code == 404

    requirements = client.get("/api/v1/hospitals/rs-pub/visit-requirements")
    assert requirements.status_code == 200
    assert requirements.json()["total"] == 1
    assert requirements.json()["items"][0]["title"] == "Persiapan uji"

    articles = client.get("/api/v1/articles")
    assert articles.status_code == 200
    assert articles.json()["total"] == 1
    assert articles.json()["items"][0]["id"] == article_id
    assert "status" not in articles.json()["items"][0]
    assert client.get(f"/api/v1/articles/{article_id}").status_code == 200
    assert (
        client.get(f"/api/v1/articles/{draft_article.json()['id']}").status_code == 404
    )


def test_public_pagination_and_validation(client, system_auth):
    for hospital_id in ("rs-1", "rs-2", "rs-3"):
        assert create_hospital(client, system_auth, hospital_id).status_code == 201
        assert (
            publish(
                client,
                system_auth,
                f"/api/v1/admin/hospitals/{hospital_id}/publish",
            ).status_code
            == 200
        )

    first = client.get("/api/v1/hospitals", params={"limit": 2})
    second = client.get("/api/v1/hospitals", params={"limit": 2, "offset": 2})
    assert first.status_code == 200
    assert first.json()["total"] == 3
    assert len(first.json()["items"]) == 2
    assert second.json()["total"] == 3
    assert len(second.json()["items"]) == 1
    assert {item["id"] for item in first.json()["items"]}.isdisjoint(
        {item["id"] for item in second.json()["items"]}
    )

    assert client.get("/api/v1/hospitals", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/hospitals", params={"limit": 101}).status_code == 422
    assert client.get("/api/v1/hospitals", params={"offset": -1}).status_code == 422
