from __future__ import annotations

from typing import Any

FUTURE_DUE = "2027-01-01T00:00:00+00:00"


def document_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Dokumen uji",
        "source": "Sumber uji sintetis",
        "owner": "Tim Uji",
        "content": "Isi dokumen uji.",
        "review_due_at": FUTURE_DUE,
    }
    payload.update(overrides)
    return payload


def create_document(client, auth, **overrides: Any):
    return client.post(
        "/api/v1/admin/knowledge-documents",
        headers=auth,
        json=document_payload(**overrides),
    )


def review(client, auth, record_id: str, decision: str, reason: str = ""):
    return client.post(
        f"/api/v1/admin/knowledge-documents/{record_id}/review",
        headers=auth,
        json={"decision": decision, "reason": reason},
    )


def test_knowledge_requires_editor_role(client, hospital_auth):
    assert client.get("/api/v1/admin/knowledge-documents").status_code == 401
    denied = client.get("/api/v1/admin/knowledge-documents", headers=hospital_auth)
    assert denied.status_code == 403


def test_knowledge_review_publish_lifecycle(client, reviewer_auth):
    created = create_document(client, reviewer_auth)
    assert created.status_code == 201
    document = created.json()
    assert document["status"] == "draft"
    assert document["version"] == 1
    assert document["reviewed_by"] is None
    assert document["is_expired"] is False
    record_id = document["id"]

    submitted = client.post(
        f"/api/v1/admin/knowledge-documents/{record_id}/submit-review",
        headers=reviewer_auth,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_review"
    resubmitted_pending = client.post(
        f"/api/v1/admin/knowledge-documents/{record_id}/submit-review",
        headers=reviewer_auth,
    )
    assert resubmitted_pending.status_code == 200

    rejected = review(client, reviewer_auth, record_id, "reject")
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"

    rejected = review(client, reviewer_auth, record_id, "reject", "Perlu perbaikan")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["reviewed_by"] == "Reviewer Medis"
    assert rejected.json()["review_reason"] == "Perlu perbaikan"

    resubmitted = client.post(
        f"/api/v1/admin/knowledge-documents/{record_id}/submit-review",
        headers=reviewer_auth,
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "pending_review"
    assert resubmitted.json()["reviewed_by"] is None
    assert resubmitted.json()["review_reason"] == ""

    approved = review(client, reviewer_auth, record_id, "approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["review_reason"] == "Disetujui untuk diterbitkan."
    idempotent = review(client, reviewer_auth, record_id, "approve")
    assert idempotent.status_code == 200
    assert idempotent.json()["status"] == "approved"
    conflicting = review(client, reviewer_auth, record_id, "reject", "Terlambat")
    assert conflicting.status_code == 409
    denied_submit = client.post(
        f"/api/v1/admin/knowledge-documents/{record_id}/submit-review",
        headers=reviewer_auth,
    )
    assert denied_submit.status_code == 409

    published = client.post(
        f"/api/v1/admin/knowledge-documents/{record_id}/publish",
        headers=reviewer_auth,
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None
    again = client.post(
        f"/api/v1/admin/knowledge-documents/{record_id}/publish",
        headers=reviewer_auth,
    )
    assert again.status_code == 200

    detail = client.get(
        f"/api/v1/admin/knowledge-documents/{record_id}", headers=reviewer_auth
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "published"

    listed = client.get(
        "/api/v1/admin/knowledge-documents",
        headers=reviewer_auth,
        params={"status": "published"},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    all_documents = client.get(
        "/api/v1/admin/knowledge-documents", headers=reviewer_auth
    )
    assert all_documents.status_code == 200
    assert all_documents.json()["total"] == 1


def test_knowledge_invalid_transitions_and_expiry(client, system_auth):
    draft = create_document(client, system_auth).json()
    publish_draft = client.post(
        f"/api/v1/admin/knowledge-documents/{draft['id']}/publish",
        headers=system_auth,
    )
    assert publish_draft.status_code == 409

    review_draft = review(client, system_auth, draft["id"], "approve")
    assert review_draft.status_code == 409

    expired = create_document(
        client,
        system_auth,
        review_due_at="2020-01-01T00:00:00+00:00",
    ).json()
    assert expired["is_expired"] is True
    assert (
        client.post(
            f"/api/v1/admin/knowledge-documents/{expired['id']}/submit-review",
            headers=system_auth,
        ).status_code
        == 200
    )
    assert review(client, system_auth, expired["id"], "approve").status_code == 200
    denied = client.post(
        f"/api/v1/admin/knowledge-documents/{expired['id']}/publish",
        headers=system_auth,
    )
    assert denied.status_code == 422
    assert "masa peninjauan" in denied.json()["error"]["message"]

    missing = client.get(
        "/api/v1/admin/knowledge-documents/tidak-ada", headers=system_auth
    )
    assert missing.status_code == 404
    missing_transition = client.post(
        "/api/v1/admin/knowledge-documents/tidak-ada/submit-review",
        headers=system_auth,
    )
    assert missing_transition.status_code == 404


def test_knowledge_versioning_supersedes_previous(client, system_auth):
    first = create_document(client, system_auth, submit_for_review=True).json()
    assert review(client, system_auth, first["id"], "approve").status_code == 200
    assert (
        client.post(
            f"/api/v1/admin/knowledge-documents/{first['id']}/publish",
            headers=system_auth,
        ).status_code
        == 200
    )

    second = create_document(
        client,
        system_auth,
        title="Dokumen uji versi 2",
        previous_version_id=first["id"],
        submit_for_review=True,
    )
    assert second.status_code == 201
    second_body = second.json()
    assert second_body["document_id"] == first["document_id"]
    assert second_body["version"] == 2
    assert second_body["previous_version_id"] == first["id"]
    assert review(client, system_auth, second_body["id"], "approve").status_code == 200
    assert (
        client.post(
            f"/api/v1/admin/knowledge-documents/{second_body['id']}/publish",
            headers=system_auth,
        ).status_code
        == 200
    )

    first_after = client.get(
        f"/api/v1/admin/knowledge-documents/{first['id']}", headers=system_auth
    )
    assert first_after.json()["status"] == "archived"

    unknown_previous = create_document(
        client, system_auth, previous_version_id="tidak-ada"
    )
    assert unknown_previous.status_code == 404


def test_knowledge_archive_and_revoke_rules(client, system_auth):
    draft = create_document(client, system_auth).json()
    denied_archive = client.post(
        f"/api/v1/admin/knowledge-documents/{draft['id']}/archive",
        headers=system_auth,
        json={"reason": "Uji"},
    )
    assert denied_archive.status_code == 409

    approved = create_document(client, system_auth, submit_for_review=True).json()
    assert review(client, system_auth, approved["id"], "approve").status_code == 200
    archived = client.post(
        f"/api/v1/admin/knowledge-documents/{approved['id']}/archive",
        headers=system_auth,
        json={"reason": "Tidak dipakai"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    again = client.post(
        f"/api/v1/admin/knowledge-documents/{approved['id']}/archive",
        headers=system_auth,
        json={"reason": "Tidak dipakai lagi"},
    )
    assert again.status_code == 200

    denied_revoke = client.post(
        f"/api/v1/admin/knowledge-documents/{approved['id']}/revoke",
        headers=system_auth,
        json={"reason": "Uji"},
    )
    assert denied_revoke.status_code == 409

    published = create_document(client, system_auth, submit_for_review=True).json()
    assert review(client, system_auth, published["id"], "approve").status_code == 200
    assert (
        client.post(
            f"/api/v1/admin/knowledge-documents/{published['id']}/publish",
            headers=system_auth,
        ).status_code
        == 200
    )
    revoked = client.post(
        f"/api/v1/admin/knowledge-documents/{published['id']}/revoke",
        headers=system_auth,
        json={"reason": "Sumber dicabut"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    again_revoke = client.post(
        f"/api/v1/admin/knowledge-documents/{published['id']}/revoke",
        headers=system_auth,
        json={"reason": "Sumber dicabut lagi"},
    )
    assert again_revoke.status_code == 200


def test_knowledge_audit_events_and_filters(client, system_auth):
    document = create_document(client, system_auth, submit_for_review=True).json()
    assert review(client, system_auth, document["id"], "approve").status_code == 200
    assert (
        client.post(
            f"/api/v1/admin/knowledge-documents/{document['id']}/publish",
            headers=system_auth,
        ).status_code
        == 200
    )

    events = client.get(
        "/api/v1/admin/audit-events",
        headers=system_auth,
        params={"object_type": "knowledge_document", "object_id": document["id"]},
    )
    assert events.status_code == 200
    actions = [item["action"] for item in events.json()["items"]]
    assert actions == ["publish", "review_approve", "create"]
    assert all(item["actor"] == "Admin Sistem" for item in events.json()["items"])
    assert all(
        item["object_type"] == "knowledge_document" for item in events.json()["items"]
    )

    publish_only = client.get(
        "/api/v1/admin/audit-events",
        headers=system_auth,
        params={"action": "publish"},
    )
    assert publish_only.status_code == 200
    assert [item["action"] for item in publish_only.json()["items"]] == ["publish"]

    paged = client.get(
        "/api/v1/admin/audit-events",
        headers=system_auth,
        params={"limit": 1, "offset": 1},
    )
    assert paged.status_code == 200
    assert paged.json()["total"] == 3
    assert len(paged.json()["items"]) == 1


def test_knowledge_synthetic_publish_denied_in_production(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.app.conftest import build_settings

    settings = build_settings(tmp_path, app_env="production")
    with TestClient(create_app(settings)) as client:
        auth = {"Authorization": "Bearer system-admin-token-0123456789abcdef"}
        created = create_document(
            client, auth, is_synthetic=True, submit_for_review=True
        )
        assert created.status_code == 201
        record_id = created.json()["id"]
        assert review(client, auth, record_id, "approve").status_code == 200
        denied = client.post(
            f"/api/v1/admin/knowledge-documents/{record_id}/publish", headers=auth
        )
        assert denied.status_code == 422
        assert "sintetis" in denied.json()["error"]["message"]


def test_audit_events_require_system_admin(client, reviewer_auth):
    denied = client.get("/api/v1/admin/audit-events", headers=reviewer_auth)
    assert denied.status_code == 403


def test_published_knowledge_is_indexed_and_hospital_scoped(client, system_auth, app):
    draft = create_document(
        client,
        system_auth,
        hospital_id="rs-a",
        content="Persiapan tes HIV meliputi konsultasi awal dan identitas diri.",
    ).json()
    assert draft["hospital_id"] == "rs-a"

    with app.state.db.connect() as connection:
        draft_chunks = connection.execute(
            "SELECT COUNT(*) FROM knowledge_chunks WHERE document_record_id = ?",
            [draft["id"]],
        ).fetchone()[0]
    assert draft_chunks == 0

    submitted = client.post(
        f"/api/v1/admin/knowledge-documents/{draft['id']}/submit-review",
        headers=system_auth,
    )
    assert submitted.status_code == 200
    assert review(client, system_auth, draft["id"], "approve").status_code == 200
    published = client.post(
        f"/api/v1/admin/knowledge-documents/{draft['id']}/publish",
        headers=system_auth,
    )
    assert published.status_code == 200

    with app.state.db.connect() as connection:
        chunks = connection.execute(
            """SELECT text FROM knowledge_chunks
               WHERE document_record_id = ?""",
            [draft["id"]],
        ).fetchall()
    assert chunks
    assert "Persiapan tes HIV" in chunks[0]["text"]
