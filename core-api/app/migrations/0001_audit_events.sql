-- Fase 0: fondasi audit administratif.
-- Tidak boleh menyimpan isi percakapan, kredensial, atau data pribadi sensitif.
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '',
    outcome TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_events_occurred_at
    ON audit_events (occurred_at);

CREATE INDEX IF NOT EXISTS idx_audit_events_object
    ON audit_events (object_type, object_id);
