from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.policy import is_expired, parse_iso, utc_now

_WORD = re.compile(r"[a-z0-9]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = frozenset(
    {
        "ada",
        "adalah",
        "agar",
        "akan",
        "aku",
        "apa",
        "apakah",
        "atau",
        "bagaimana",
        "bagi",
        "bahwa",
        "bisa",
        "boleh",
        "dalam",
        "dan",
        "dapat",
        "dari",
        "dengan",
        "di",
        "dia",
        "ini",
        "ingin",
        "itu",
        "jika",
        "juga",
        "kah",
        "kamu",
        "karena",
        "ke",
        "kepada",
        "kita",
        "mau",
        "mereka",
        "nya",
        "oleh",
        "pada",
        "para",
        "saya",
        "sebagai",
        "sebuah",
        "seperti",
        "sudah",
        "tentang",
        "tersebut",
        "tidak",
        "untuk",
        "yaitu",
        "yang",
        "the",
        "and",
        "are",
        "for",
        "from",
        "how",
        "is",
        "of",
        "should",
        "that",
        "this",
        "to",
        "what",
        "with",
    }
)


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    record_id: str
    document_id: str
    title: str
    version: int
    source: str
    published_at: str | None
    chunk_index: int
    text: str
    score: float
    hospital_id: str | None


def chunk_text(text: str, *, max_chars: int = 700) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE.split(normalized):
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                sentence[start : start + max_chars]
                for start in range(0, len(sentence), max_chars)
            )
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()]


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in _WORD.findall(text.lower())
        if token not in _STOPWORDS and len(token) > 1
    ]


def _score(query_terms: set[str], title: str, text: str) -> float:
    if not query_terms:
        return 0.0
    document_terms = set(tokenize(f"{title} {text}"))
    matched = query_terms & document_terms
    return len(matched) / len(query_terms)


def index_document(
    connection: sqlite3.Connection,
    record: Mapping[str, Any],
    *,
    now: str | None = None,
) -> int:
    record_id = str(record["id"])
    chunks = chunk_text(str(record["content"]))
    timestamp = now or utc_now().isoformat()
    connection.execute(
        "DELETE FROM knowledge_chunks WHERE document_record_id = ?",
        [record_id],
    )
    for index, text in enumerate(chunks):
        connection.execute(
            """INSERT INTO knowledge_chunks (
                id, document_record_id, document_id, version, chunk_index,
                text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                f"{record_id}:{index}",
                record_id,
                str(record["document_id"]),
                int(record["version"]),
                index,
                text,
                timestamp,
            ),
        )
    return len(chunks)


def ensure_published_indexed(
    connection: sqlite3.Connection, *, now: str | None = None
) -> int:
    rows = connection.execute(
        """SELECT d.* FROM knowledge_documents d
           WHERE d.status = 'published'
             AND NOT EXISTS (
                 SELECT 1 FROM knowledge_chunks c
                 WHERE c.document_record_id = d.id
             )"""
    ).fetchall()
    timestamp = now or utc_now().isoformat()
    for row in rows:
        index_document(connection, dict(row), now=timestamp)
    return len(rows)


def retrieve(
    connection: sqlite3.Connection,
    query: str,
    *,
    hospital_id: str | None = None,
    top_k: int = 4,
    threshold: float = 0.2,
    now: datetime | None = None,
) -> list[RetrievedChunk]:
    query_terms = set(tokenize(query))
    if not query_terms:
        return []
    moment = now or utc_now()
    rows = connection.execute(
        """SELECT c.document_record_id, c.document_id, c.version,
                  c.chunk_index, c.text,
                  d.title, d.source, d.published_at, d.effective_from,
                  d.review_due_at, d.hospital_id
           FROM knowledge_chunks c
           JOIN knowledge_documents d ON d.id = c.document_record_id
           WHERE d.status = 'published'"""
    ).fetchall()

    results: list[RetrievedChunk] = []
    for row in rows:
        if hospital_id and row["hospital_id"] not in (None, hospital_id):
            continue
        effective_from = parse_iso(row["effective_from"])
        if effective_from is not None and effective_from > moment:
            continue
        if is_expired(row["review_due_at"], now=moment):
            continue
        score = _score(query_terms, str(row["title"]), str(row["text"]))
        if score <= 0 or score < threshold:
            continue
        results.append(
            RetrievedChunk(
                record_id=str(row["document_record_id"]),
                document_id=str(row["document_id"]),
                title=str(row["title"]),
                version=int(row["version"]),
                source=str(row["source"]),
                published_at=(
                    str(row["published_at"]) if row["published_at"] else None
                ),
                chunk_index=int(row["chunk_index"]),
                text=str(row["text"]),
                score=score,
                hospital_id=(str(row["hospital_id"]) if row["hospital_id"] else None),
            )
        )

    def sort_key(chunk: RetrievedChunk) -> tuple[float, float, str, int]:
        published = parse_iso(chunk.published_at)
        return (
            -chunk.score,
            -(published.timestamp() if published else 0.0),
            chunk.document_id,
            chunk.chunk_index,
        )

    results.sort(key=sort_key)
    return results[:top_k]
