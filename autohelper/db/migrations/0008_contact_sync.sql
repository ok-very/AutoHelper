-- Contact Sync tables
-- M8: State tracking, audit log, and per-contact hash tracking

-- Singleton row tracking last file hash and sync status
CREATE TABLE contact_sync_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    file_hash TEXT,
    last_sync_at TEXT,
    last_status TEXT,
    created_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    deleted_count INTEGER NOT NULL DEFAULT 0
);

-- Append-only audit log per sync run
CREATE TABLE contact_sync_log (
    sync_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,  -- 'completed', 'failed', 'skipped', 'dry_run'
    created INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT,       -- JSON array of error strings
    dry_run INTEGER NOT NULL DEFAULT 0,
    file_hash TEXT,
    csv_row_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_contact_sync_log_at ON contact_sync_log(started_at);

-- Per-contact tracking: maps CSV email to Exchange identity, tracks row hash
CREATE TABLE contact_sync_contacts (
    email_primary TEXT PRIMARY KEY,
    row_hash TEXT NOT NULL,
    exchange_identity TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
