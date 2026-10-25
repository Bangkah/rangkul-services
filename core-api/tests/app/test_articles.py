from __future__ import annotations

from tests.app.test_public_catalog import article_payload, publish


def test_articles_require_editor_role(client, hospital_auth):
    assert client.get("/api/v1/admin/articles").status_code == 401
    assert (
        client.get("/api/v1/admin/articles", headers=hospital_auth).status_code == 403
    )


def test_article_lifecycle_and_publication(client, reviewer_auth):
    created = client.post(
        "/api/v1/admin/articles",
        headers=reviewer_auth,
        json={"title": "Artikel tanpa isi"},
    )
    assert created.status_code == 201
    article = created.json()
    assert article["status"] == "draft"
    assert article["published_at"] is None
    article_id = article["id"]

    invalid = publish(
        client, reviewer_auth, f"/api/v1/admin/articles/{article_id}/publish"
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    patched = client.patch(
        f"/api/v1/admin/articles/{article_id}",
        headers=reviewer_auth,
        json={
            "content": "Isi artikel lengkap.",
            "source": "Sumber uji",
            "reference_url": "https://contoh.invalid/artikel",
        },
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "draft"

    published = publish(
        client, reviewer_auth, f"/api/v1/admin/articles/{article_id}/publish"
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None
    again = publish(
        client, reviewer_auth, f"/api/v1/admin/articles/{article_id}/publish"
    )
    assert again.status_code == 200
    assert client.get("/api/v1/articles").json()["total"] == 1
    assert client.get(f"/api/v1/articles/{article_id}").status_code == 200

    edited = client.patch(
        f"/api/v1/admin/articles/{article_id}",
        headers=reviewer_auth,
        json={"summary": "Ringkasan baru", "is_synthetic": True},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "draft"
    assert edited.json()["published_at"] is None
    assert edited.json()["is_synthetic"] is True
    assert client.get(f"/api/v1/articles/{article_id}").status_code == 404

    archived = client.post(
        f"/api/v1/admin/articles/{article_id}/archive",
        headers=reviewer_auth,
        json={"reason": "Uji arsip"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    again = client.post(
        f"/api/v1/admin/articles/{article_id}/archive",
        headers=reviewer_auth,
        json={"reason": "Uji arsip ulang"},
    )
    assert again.status_code == 200


def test_article_admin_list_filters_and_errors(client, system_auth):
    first = client.post(
        "/api/v1/admin/articles",
        headers=system_auth,
        json=article_payload(title="Artikel satu"),
    )
    second = client.post(
        "/api/v1/admin/articles",
        headers=system_auth,
        json=article_payload(title="Artikel dua"),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert (
        publish(
            client,
            system_auth,
            f"/api/v1/admin/articles/{first.json()['id']}/publish",
        ).status_code
        == 200
    )

    published = client.get(
        "/api/v1/admin/articles", headers=system_auth, params={"status": "published"}
    )
    assert published.status_code == 200
    assert [item["id"] for item in published.json()["items"]] == [first.json()["id"]]
    drafts = client.get(
        "/api/v1/admin/articles", headers=system_auth, params={"status": "draft"}
    )
    assert drafts.json()["total"] == 1
    assert (
        client.get(
            "/api/v1/admin/articles", headers=system_auth, params={"status": "x"}
        ).status_code
        == 422
    )

    assert (
        client.get("/api/v1/admin/articles/tidak-ada", headers=system_auth).status_code
        == 404
    )
    assert (
        client.patch(
            "/api/v1/admin/articles/tidak-ada",
            headers=system_auth,
            json={"title": "X"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/admin/articles/{first.json()['id']}",
            headers=system_auth,
            json={},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/admin/articles/{first.json()['id']}",
            headers=system_auth,
            json={"tidak_ada": "X"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/admin/articles/tidak-ada/publish", headers=system_auth
        ).status_code
        == 404
    )
