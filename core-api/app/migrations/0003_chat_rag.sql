-- Fase 2: indeks teks untuk RAG dan cakupan fasilitas dokumen pengetahuan.
-- Chunk adalah turunan dari dokumen; dokumen tetap sumber kebenaran.
ALTER TABLE knowledge_documents ADD COLUMN hospital_id TEXT;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    document_record_id TEXT NOT NULL
        REFERENCES knowledge_documents (id) ON DELETE CASCADE,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (document_record_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document
    ON knowledge_chunks (document_record_id, chunk_index);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_hospital
    ON knowledge_documents (hospital_id, status);
