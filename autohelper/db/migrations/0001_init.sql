-- Initial schema for AutoHelper
-- M0: Core tables for roots, files, index runs, audit log

-- Configured root directories
CREATE TABLE roots (
    root_id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexed files
CREATE TABLE files (
    file_id TEXT PRIMARY KEY,
    root_id TEXT NOT NULL,
    canonical_path TEXT NOT NULL UNIQUE,
    rel_path TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    content_hash TEXT,
    indexed_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_dir INTEGER NOT NULL DEFAULT 0,
    ext TEXT NOT NULL DEFAULT '',
    mime TEXT,
    FOREIGN KEY (root_id) REFERENCES roots(root_id) ON DELETE CASCADE
);

-- Indices for file queries
CREATE INDEX idx_files_root ON files(root_id);
CREATE INDEX idx_files_ext ON files(ext);
CREATE INDEX idx_files_path ON files(canonical_path);

-- Index run tracking
CREATE TABLE index_runs (
    index_run_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,  -- 'full', 'incremental', 'rescan'
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',  -- 'running', 'completed', 'failed', 'cancelled'
    stats_json TEXT  -- JSON blob with counts, errors, timing
);

-- Per-root index state
CREATE TABLE index_state (
    root_id TEXT PRIMARY KEY,
    last_full_scan_at TEXT,
    last_rescan_at TEXT,
    FOREIGN KEY (root_id) REFERENCES roots(root_id) ON DELETE CASCADE
);

-- References (traceability links from AutoArt)
CREATE TABLE refs (
    ref_id TEXT PRIMARY KEY,
    work_item_id TEXT,
    context_id TEXT,
    file_id TEXT,
    canonical_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT NOT NULL DEFAULT 'system',
    note TEXT,
    FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE SET NULL
);

CREATE INDEX idx_refs_work_item ON refs(work_item_id);
CREATE INDEX idx_refs_context ON refs(context_id);
CREATE INDEX idx_refs_file ON refs(file_id);

-- Audit log (append-only)
CREATE TABLE audit_log (
    audit_id TEXT PRIMARY KEY,
    at TEXT NOT NULL DEFAULT (datetime('now')),
    actor TEXT NOT NULL DEFAULT 'system',
    verb TEXT NOT NULL,
    work_item_id TEXT,
    context_id TEXT,
    request_json TEXT,
    result_json TEXT,
    before_path TEXT,
    after_path TEXT,
    status TEXT NOT NULL DEFAULT 'success',  -- 'success', 'error'
    error_code TEXT,
    idempotency_key TEXT
);

CREATE INDEX idx_audit_at ON audit_log(at);
CREATE INDEX idx_audit_work_item ON audit_log(work_item_id);
CREATE INDEX idx_audit_idempotency ON audit_log(idempotency_key);
