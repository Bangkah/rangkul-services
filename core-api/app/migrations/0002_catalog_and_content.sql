-- Fase 1: katalog fasilitas, konten, dan dokumen pengetahuan.
-- Tidak ada data sintetis di migrasi; gunakan `python -m app.seed` untuk data pengembangan.
CREATE TABLE IF NOT EXISTS hospitals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    latitude REAL,
    longitude REAL,
    contact_phone TEXT NOT NULL DEFAULT '',
    contact_email TEXT NOT NULL DEFAULT '',
    operating_hours TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    source TEXT NOT NULL DEFAULT '',
    verified_at TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0
        CHECK (is_synthetic IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),
    CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180))
);

CREATE INDEX IF NOT EXISTS idx_hospitals_status ON hospitals (status);

CREATE TABLE IF NOT EXISTS hospital_services (
    id TEXT PRIMARY KEY,
    hospital_id TEXT NOT NULL REFERENCES hospitals (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    requirements TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    source TEXT NOT NULL DEFAULT '',
    verified_at TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0
        CHECK (is_synthetic IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hospital_services_hospital
    ON hospital_services (hospital_id, status);

CREATE TABLE IF NOT EXISTS visit_requirements (
    id TEXT PRIMARY KEY,
    hospital_id TEXT NOT NULL REFERENCES hospitals (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    source TEXT NOT NULL DEFAULT '',
    verified_at TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0
        CHECK (is_synthetic IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_visit_requirements_hospital
    ON visit_requirements (hospital_id, status, sort_order);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    owner TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (
            status IN (
                'draft',
                'pending_review',
                'approved',
                'rejected',
                'published',
                'archived',
                'revoked'
            )
        ),
    content TEXT NOT NULL,
    effective_from TEXT,
    review_due_at TEXT,
    previous_version_id TEXT REFERENCES knowledge_documents (id),
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_reason TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0
        CHECK (is_synthetic IN (0, 1)),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (document_id, version),
    CHECK (previous_version_id IS NULL OR previous_version_id <> id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_document
    ON knowledge_documents (document_id, version);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_status
    ON knowledge_documents (status);

CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    reference_url TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    published_at TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0
        CHECK (is_synthetic IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_status ON articles (status, published_at);
