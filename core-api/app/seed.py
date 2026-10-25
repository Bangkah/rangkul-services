from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.db import Database

SYNTHETIC_SOURCE = "SEED PENGEMBANGAN - data sintetis, bukan data resmi"
SEED_HOSPITAL_ID = "rs-pilot-demo"


def _seed_statements(now: str) -> list[tuple[str, tuple[Any, ...]]]:
    return [
        (
            """INSERT INTO hospitals (
                id, name, address, latitude, longitude, contact_phone,
                contact_email, operating_hours, status, source, verified_at,
                is_synthetic, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'published', ?, ?, 1, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                SEED_HOSPITAL_ID,
                "RS Pilot Demo (Data Sintetis)",
                "Jl. Contoh No. 1, Lhokseumawe (alamat sintetis)",
                5.180100,
                97.150700,
                "+62-000-0000-0000 (contoh)",
                "contoh@rs-pilot.invalid",
                "Senin-Jumat 08.00-16.00 (contoh)",
                SYNTHETIC_SOURCE,
                "2026-10-01T00:00:00+00:00",
                now,
                now,
            ),
        ),
        (
            """INSERT INTO hospital_services (
                id, hospital_id, name, description, requirements, status,
                source, verified_at, is_synthetic, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'published', ?, ?, 1, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                "svc-demo-konsultasi",
                SEED_HOSPITAL_ID,
                "Konsultasi HIV dan IMS (Contoh)",
                "Layanan konsultasi contoh untuk pengembangan antarmuka.",
                "Membawa identitas diri (contoh).",
                SYNTHETIC_SOURCE,
                "2026-10-01T00:00:00+00:00",
                now,
                now,
            ),
        ),
        (
            """INSERT INTO hospital_services (
                id, hospital_id, name, description, requirements, status,
                source, verified_at, is_synthetic, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'published', ?, ?, 1, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                "svc-demo-tes-hiv",
                SEED_HOSPITAL_ID,
                "Tes HIV Sukarela (Contoh)",
                "Alur tes HIV sukarela dengan pendampingan konselor (contoh).",
                "Konsultasi awal sebelum tes (contoh).",
                SYNTHETIC_SOURCE,
                "2026-10-01T00:00:00+00:00",
                now,
                now,
            ),
        ),
        (
            """INSERT INTO visit_requirements (
                id, hospital_id, title, description, sort_order, status,
                source, verified_at, is_synthetic, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, 'published', ?, ?, 1, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                "visit-demo-identitas",
                SEED_HOSPITAL_ID,
                "Membawa identitas diri (contoh)",
                "Persyaratan contoh; konfirmasi ulang dengan petugas fasilitas.",
                SYNTHETIC_SOURCE,
                "2026-10-01T00:00:00+00:00",
                now,
                now,
            ),
        ),
        (
            """INSERT INTO visit_requirements (
                id, hospital_id, title, description, sort_order, status,
                source, verified_at, is_synthetic, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 2, 'published', ?, ?, 1, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                "visit-demo-jadwal",
                SEED_HOSPITAL_ID,
                "Datang sesuai jam layanan (contoh)",
                "Jam layanan pada seed ini sintetis dan bukan jadwal resmi.",
                SYNTHETIC_SOURCE,
                "2026-10-01T00:00:00+00:00",
                now,
                now,
            ),
        ),
        (
            """INSERT INTO knowledge_documents (
                id, document_id, title, source, owner, version, status, content,
                review_due_at, reviewed_by, reviewed_at, review_reason,
                published_at, is_synthetic, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, 'published', ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                "kdoc-demo-kunjungan-v1",
                "kdoc-demo-kunjungan",
                "Panduan kunjungan contoh",
                "Materi edukasi sintetis untuk pengembangan",
                "Tim RANGKUL (contoh)",
                "Persiapan kunjungan dapat berbeda antar fasilitas. "
                "Data ini hanya contoh pengembangan.",
                "2027-10-01T00:00:00+00:00",
                "Reviewer Medis (Simulasi)",
                "2026-10-02T00:00:00+00:00",
                "Disetujui untuk data uji.",
                "2026-10-03T00:00:00+00:00",
                "seed",
                now,
                now,
            ),
        ),
        (
            """INSERT INTO knowledge_documents (
                id, document_id, title, source, owner, version, status, content,
                is_synthetic, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, 'pending_review', ?, 1, 'seed', ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                "kdoc-demo-edukasi-v1",
                "kdoc-demo-edukasi",
                "Informasi edukasi HIV contoh",
                "Materi edukasi sintetis untuk pengembangan",
                "Tim RANGKUL (contoh)",
                "Dokumen ini masih menunggu peninjauan dan tidak boleh "
                "dipakai sebagai sumber jawaban.",
                now,
                now,
            ),
        ),
        (
            """INSERT INTO articles (
                id, title, summary, content, source, reference_url, status,
                published_at, is_synthetic, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '', 'published', ?, 1, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                "article-demo-persiapan",
                "Persiapan kunjungan (contoh)",
                "Ringkasan contoh untuk integrasi frontend.",
                "Artikel ini adalah data sintetis pengembangan. "
                "Persyaratan resmi harus dikonfirmasi kepada fasilitas.",
                SYNTHETIC_SOURCE,
                "2026-10-04T00:00:00+00:00",
                now,
                now,
            ),
        ),
        (
            """INSERT INTO articles (
                id, title, summary, content, source, reference_url, status,
                is_synthetic, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '', 'draft', 1, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                "article-demo-draf",
                "Draf artikel contoh",
                "Artikel ini tidak boleh tampil di API publik.",
                "Draf sintetis untuk menguji filter status publikasi.",
                SYNTHETIC_SOURCE,
                now,
                now,
            ),
        ),
    ]


def seed(connection: sqlite3.Connection, *, now: str | None = None) -> dict[str, int]:
    timestamp = now or datetime.now(timezone.utc).isoformat()
    inserted = 0
    skipped = 0
    for statement, params in _seed_statements(timestamp):
        cursor = connection.execute(statement, params)
        if cursor.rowcount:
            inserted += 1
        else:
            skipped += 1
    return {"inserted": inserted, "skipped": skipped}


def main() -> int:
    settings = Settings.from_env()
    if settings.is_production:
        print(
            "Seed sintetis ditolak: data pengembangan tidak boleh masuk produksi.",
            file=sys.stderr,
        )
        return 2
    database = Database(settings.database_path)
    database.migrate()
    with database.connect() as connection:
        result = seed(connection)
        connection.commit()
    print(
        f"Seed sintetis selesai: {result['inserted']} dibuat, "
        f"{result['skipped']} dilewati."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
