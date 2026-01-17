-- File Aliases: Track historical paths for files to enable search by old name
CREATE TABLE file_aliases (
    alias_id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    old_canonical_path TEXT NOT NULL,
    new_canonical_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    detected_by TEXT DEFAULT 'rename_detection',
    FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE,
    UNIQUE(file_id, old_canonical_path)
);

CREATE INDEX idx_aliases_file_id ON file_aliases(file_id);
CREATE INDEX idx_aliases_old_path ON file_aliases(old_canonical_path);
