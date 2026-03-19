-- Contact Hub — canonical contact records and project associations
-- M14: Central resolution layer for contacts across ClickUp, Exchange, templates, and mail triage

-- Canonical contact record — the single source of truth for contact data
CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    full_name TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    job_title TEXT NOT NULL DEFAULT '',
    email_primary TEXT NOT NULL,
    email_secondary TEXT,
    phone_business TEXT,
    phone_mobile TEXT,
    category TEXT NOT NULL DEFAULT '',
    notes TEXT,
    confidence TEXT NOT NULL DEFAULT 'MEDIUM',  -- HIGH, MEDIUM, LOW
    staleness_label TEXT NOT NULL DEFAULT 'Active',  -- Active, Aging, Dormant
    last_seen TEXT,

    -- Sync identifiers — this is what makes it a hub, not a leaf
    exchange_id TEXT,
    clickup_contact_ref TEXT,

    -- Source tracking
    source TEXT NOT NULL DEFAULT 'manual',  -- import, exchange, clickup, manual
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email_primary);
CREATE INDEX IF NOT EXISTS idx_contacts_category ON contacts(category);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company);
CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(full_name);

-- Links contacts to projects with a role
CREATE TABLE IF NOT EXISTS project_contact_associations (
    id TEXT PRIMARY KEY,
    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- developer, city_planner, artist, panel_member,
                        -- architect, landscape_architect, community_advisor,
                        -- indigenous_advisor, project_coordinator
    is_primary INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pca_contact ON project_contact_associations(contact_id);
CREATE INDEX IF NOT EXISTS idx_pca_project ON project_contact_associations(project_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pca_unique_role ON project_contact_associations(contact_id, project_id, role);
