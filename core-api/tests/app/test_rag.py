from __future__ import annotations

from app import rag, seed
from app.db import Database


def test_chunk_text_respects_limit():
    text = " ".join(["Kalimat pendek."] * 200)

    chunks = rag.chunk_text(text, max_chars=700)

    assert chunks
    assert all(len(chunk) <= 700 for chunk in chunks)
    assert " ".join(chunks) == " ".join(text.split())


def test_seed_indexes_only_published_documents(tmp_path):
    database = Database(tmp_path / "rag.sqlite3")
    database.migrate()

    with database.connect() as connection:
        seed.seed(connection, now="2026-10-01T00:00:00+00:00")
        indexed = rag.ensure_published_indexed(connection)
        connection.commit()

        assert indexed == 0
        published_chunks = connection.execute(
            """SELECT COUNT(*) FROM knowledge_chunks c
               JOIN knowledge_documents d ON d.id = c.document_record_id
               WHERE d.status = 'published'"""
        ).fetchone()[0]
        pending_chunks = connection.execute(
            """SELECT COUNT(*) FROM knowledge_chunks c
               JOIN knowledge_documents d ON d.id = c.document_record_id
               WHERE d.status = 'pending_review'"""
        ).fetchone()[0]

    assert published_chunks > 0
    assert pending_chunks == 0


def test_retrieve_returns_relevant_published_source(tmp_path):
    database = Database(tmp_path / "retrieve.sqlite3")
    database.migrate()

    with database.connect() as connection:
        seed.seed(connection, now="2026-10-01T00:00:00+00:00")
        results = rag.retrieve(
            connection,
            "Apa persiapan tes HIV?",
            top_k=4,
            threshold=0.2,
        )

    assert results
    assert results[0].document_id == "kdoc-demo-tes-hiv"
    assert results[0].title == "Persiapan tes HIV (contoh)"
    assert results[0].score >= 0.2
    assert results[0].published_at is not None
    assert all(result.document_id != "kdoc-demo-edukasi" for result in results)


def test_retrieve_abstains_when_threshold_not_met(tmp_path):
    database = Database(tmp_path / "threshold.sqlite3")
    database.migrate()

    with database.connect() as connection:
        seed.seed(connection, now="2026-10-01T00:00:00+00:00")
        results = rag.retrieve(
            connection,
            "Apa persiapan tes HIV?",
            threshold=1.1,
        )

    assert results == []


def test_retrieve_excludes_expired_review(tmp_path):
    database = Database(tmp_path / "expired.sqlite3")
    database.migrate()

    with database.connect() as connection:
        seed.seed(connection, now="2026-10-01T00:00:00+00:00")
        connection.execute(
            """UPDATE knowledge_documents
               SET review_due_at = '2020-01-01T00:00:00+00:00'
               WHERE document_id = 'kdoc-demo-tes-hiv'"""
        )
        results = rag.retrieve(
            connection,
            "Apa persiapan tes HIV?",
            threshold=0.2,
        )

    assert all(result.document_id != "kdoc-demo-tes-hiv" for result in results)


def test_retrieve_filters_other_hospital_scope(tmp_path):
    database = Database(tmp_path / "hospital.sqlite3")
    database.migrate()

    with database.connect() as connection:
        seed.seed(connection, now="2026-10-01T00:00:00+00:00")
        connection.execute(
            """UPDATE knowledge_documents
               SET hospital_id = 'rs-b'
               WHERE document_id = 'kdoc-demo-tes-hiv'"""
        )
        connection.execute("DELETE FROM knowledge_chunks")
        rag.ensure_published_indexed(connection)
        other = rag.retrieve(
            connection,
            "Apa persiapan tes HIV?",
            hospital_id="rs-a",
            threshold=0.2,
        )
        matching = rag.retrieve(
            connection,
            "Apa persiapan tes HIV?",
            hospital_id="rs-b",
            threshold=0.2,
        )

    assert all(result.document_id != "kdoc-demo-tes-hiv" for result in other)
    assert any(result.document_id == "kdoc-demo-tes-hiv" for result in matching)
