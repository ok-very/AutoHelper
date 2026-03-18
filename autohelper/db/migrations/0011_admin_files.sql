-- Admin files discovered in non-artist folders (Correspondence, Emails, etc.)
CREATE TABLE IF NOT EXISTS admin_files (
    file_id             TEXT PRIMARY KEY,
    file_path           TEXT NOT NULL,
    folder_name         TEXT NOT NULL,
    category            TEXT NOT NULL,
    nation              TEXT,
    file_type           TEXT,
    candidate_artist_id TEXT,
    match_score         REAL,
    attributed_to       TEXT,
    scan_run_id         TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_admin_files_attributed ON admin_files(attributed_to);
CREATE INDEX IF NOT EXISTS idx_admin_files_candidate ON admin_files(candidate_artist_id);
