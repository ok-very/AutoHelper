-- Artist Records tables
-- M9: Artist manifest cache, folder tracking, and scan history

-- One row per unique artist (canonical, after cross-category dedup)
CREATE TABLE IF NOT EXISTS artists (
    artist_id       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    first_name      TEXT,
    last_name       TEXT,
    manifest_json   TEXT NOT NULL,          -- full ArtistManifest as JSON
    completeness    REAL NOT NULL DEFAULT 0.0,
    has_bio         INTEGER NOT NULL DEFAULT 0,
    has_cv          INTEGER NOT NULL DEFAULT 0,
    has_tearsheet   INTEGER NOT NULL DEFAULT 0,
    has_contact     INTEGER NOT NULL DEFAULT 0,
    has_images      INTEGER NOT NULL DEFAULT 0,
    review_status   TEXT NOT NULL DEFAULT 'pending',
    primary_folder  TEXT NOT NULL,
    categories      TEXT NOT NULL DEFAULT '[]',     -- JSON array
    identity_tags   TEXT NOT NULL DEFAULT '[]',     -- JSON array
    nations         TEXT NOT NULL DEFAULT '[]',     -- JSON array
    scanned_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(display_name);
CREATE INDEX IF NOT EXISTS idx_artists_completeness ON artists(completeness);
CREATE INDEX IF NOT EXISTS idx_artists_review ON artists(review_status);

-- Maps every physical folder to its artist (many folders -> one artist)
CREATE TABLE IF NOT EXISTS artist_folders (
    folder_id       TEXT PRIMARY KEY,
    artist_id       TEXT NOT NULL,
    folder_path     TEXT NOT NULL UNIQUE,
    category        TEXT NOT NULL,      -- 'indigenous','public','private','corporate'
    layout          TEXT NOT NULL,      -- 'nation_based','bucketed','flat'
    nation          TEXT,               -- only for nation_based layouts
    is_primary      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_artist_folders_artist ON artist_folders(artist_id);
CREATE INDEX IF NOT EXISTS idx_artist_folders_path ON artist_folders(folder_path);

-- Scan run history (mirrors index_runs pattern)
CREATE TABLE IF NOT EXISTS artist_scan_runs (
    run_id      TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,      -- 'full','incremental','single_artist'
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'running',
    stats_json  TEXT
);

CREATE INDEX IF NOT EXISTS idx_artist_scan_runs_status ON artist_scan_runs(status);
