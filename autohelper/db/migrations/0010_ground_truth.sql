-- Ground truth contacts reference table (imported from CSV)
CREATE TABLE IF NOT EXISTS ground_truth_contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name      TEXT,
    last_name       TEXT,
    norm_first      TEXT NOT NULL,
    norm_last       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    company         TEXT,
    job_title       TEXT,
    categories      TEXT,
    is_artist       INTEGER NOT NULL DEFAULT 0,
    artist_domains  TEXT,
    notes           TEXT,
    imported_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gt_name ON ground_truth_contacts(norm_last, norm_first);
CREATE INDEX IF NOT EXISTS idx_gt_artist ON ground_truth_contacts(is_artist);

-- Add domain-pass metadata to artist_folders
ALTER TABLE artist_folders ADD COLUMN domain_source TEXT;
ALTER TABLE artist_folders ADD COLUMN confidence REAL DEFAULT 0.8;

-- Add ground truth match flag to artists
ALTER TABLE artists ADD COLUMN ground_truth_matched INTEGER NOT NULL DEFAULT 0;
ALTER TABLE artists ADD COLUMN domain_sources TEXT NOT NULL DEFAULT '[]';
