-- Migration: 0004_mail_transient.sql
-- Description: Create tables for tracking mail ingestion and storing transient email data

-- Log of PST/OST ingestion events
CREATE TABLE IF NOT EXISTS mail_ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    email_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending', -- pending, completed, failed
    error_message TEXT
);

-- Transient storage for ingested emails
-- These are meant to be temporary until synced or processed
CREATE TABLE IF NOT EXISTS transient_emails (
    id TEXT PRIMARY KEY, -- EntryID or unique hash
    subject TEXT,
    sender TEXT,
    received_at DATETIME,
    project_id TEXT, -- Extracted Project ID
    body_preview TEXT,
    
    -- Metadata stored as JSON
    -- Includes: priority, action_type, keywords, etc.
    metadata JSON,
    
    ingestion_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (ingestion_id) REFERENCES mail_ingestion_log(id) ON DELETE CASCADE
);

-- Index for quick lookup by project or date
CREATE INDEX IF NOT EXISTS idx_transient_emails_project ON transient_emails(project_id);
CREATE INDEX IF NOT EXISTS idx_transient_emails_date ON transient_emails(received_at);
