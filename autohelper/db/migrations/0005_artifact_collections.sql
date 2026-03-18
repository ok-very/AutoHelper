-- Migration: 0005_artifact_collections.sql
-- Description: Create tables for tracking artifact collections and collected artifacts
-- These tables provide database-level tracking alongside the JSON manifest files

-- Collection sessions - tracks each artifact collection run
CREATE TABLE IF NOT EXISTS artifact_collections (
    collection_id TEXT PRIMARY KEY,
    manifest_path TEXT UNIQUE NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('web', 'local')),
    source_url TEXT,
    source_path TEXT,
    output_folder TEXT NOT NULL,
    naming_template TEXT DEFAULT '{index}_{hash}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    artifact_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted'))
);

-- Collected artifacts - individual items from collection sessions
-- Links to files table when files are indexed
CREATE TABLE IF NOT EXISTS collected_artifacts (
    artifact_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    file_id TEXT,
    content_hash TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    current_filename TEXT NOT NULL,
    source_url TEXT,
    source_path TEXT,
    collected_at TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT DEFAULT '{}',
    FOREIGN KEY (collection_id) REFERENCES artifact_collections(collection_id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE SET NULL
);

-- Indices for efficient lookups
CREATE INDEX IF NOT EXISTS idx_artifact_collections_output ON artifact_collections(output_folder);
CREATE INDEX IF NOT EXISTS idx_artifact_collections_status ON artifact_collections(status);
CREATE INDEX IF NOT EXISTS idx_artifact_collections_created ON artifact_collections(created_at);

CREATE INDEX IF NOT EXISTS idx_collected_artifacts_collection ON collected_artifacts(collection_id);
CREATE INDEX IF NOT EXISTS idx_collected_artifacts_hash ON collected_artifacts(content_hash);
CREATE INDEX IF NOT EXISTS idx_collected_artifacts_file ON collected_artifacts(file_id);
CREATE INDEX IF NOT EXISTS idx_collected_artifacts_collected ON collected_artifacts(collected_at);
