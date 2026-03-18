-- BFA Todo: migrate from YAML files to SQLite

CREATE TABLE bfa_projects (
    uid             TEXT PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    fingerprint     TEXT,
    type            TEXT NOT NULL DEFAULT 'project',
    status          TEXT NOT NULL DEFAULT 'active',
    source          TEXT,
    fields_json     TEXT NOT NULL DEFAULT '{}',
    header_text     TEXT,
    header_html     TEXT,
    phase_display   TEXT,
    phase_canonical TEXT,
    next_steps_json TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE bfa_sections (
    project_uid TEXT NOT NULL REFERENCES bfa_projects(uid) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    text        TEXT,
    html        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (project_uid, name)
);

CREATE TABLE bfa_aliases (
    id                  INTEGER PRIMARY KEY DEFAULT 1,
    version             INTEGER NOT NULL DEFAULT 1,
    mappings_json       TEXT NOT NULL DEFAULT '[]',
    rollups_json        TEXT NOT NULL DEFAULT '[]',
    ignored_json        TEXT NOT NULL DEFAULT '[]',
    client_aliases_json TEXT NOT NULL DEFAULT '{}',
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_bfa_projects_status ON bfa_projects(status);
CREATE INDEX idx_bfa_projects_type ON bfa_projects(type);
CREATE INDEX idx_bfa_sections_uid ON bfa_sections(project_uid);
