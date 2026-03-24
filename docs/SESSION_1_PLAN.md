# Session 1: Foundation Scaffold

## Goal

Add the schema capture layer to BFA without breaking existing functionality. After this session, every project upsert produces JSON-LD and lifecycle events are recorded as first-class data.

## Changes

### 1. Migration: `bfa_project_events`

**File:** `autohelper/db/migrations/0018_project_events_and_schema.sql`

```sql
CREATE TABLE IF NOT EXISTS bfa_project_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uid TEXT NOT NULL REFERENCES bfa_projects(uid) ON DELETE CASCADE,
    event_type TEXT NOT NULL,   -- on_hold, reinitiated, phase_change, contact_change,
                                -- name_change, budget_change, status_change, created, archived
    event_date TEXT NOT NULL DEFAULT (datetime('now')),
    previous_value TEXT,
    new_value TEXT,
    source TEXT NOT NULL DEFAULT 'manual',  -- manual, clickup, agent, ingestion
    agent_session TEXT,         -- conversation/session ID that produced this event
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bfa_events_project ON bfa_project_events(project_uid);
CREATE INDEX IF NOT EXISTS idx_bfa_events_type ON bfa_project_events(event_type);

-- JSON-LD compiled schema on bfa_projects
ALTER TABLE bfa_projects ADD COLUMN schema_json TEXT;
```

### 2. Schema compiler

**File:** `autohelper/modules/bfa_todo/schema.py` (NEW)

Public functions:
- `compile_project_schema(entry: dict) -> dict` — flat fields + sections + events → JSON-LD
- `diff_schemas(old: dict, new: dict) -> list[dict]` — structural diff → list of change descriptors
- `emit_events_from_diff(project_uid: str, changes: list[dict], source: str)` — write events to DB
- `validate_schema(schema: dict) -> list[str]` — return list of validation errors (empty = valid)

Helper functions:
- `_compile_org(client_name: str, fields: dict) -> dict` — build Organization entity
- `_compile_contacts(contacts_section: dict) -> list[dict]` — parse contacts section → Person entities
- `_compile_budget(fields: dict) -> dict` — budget strings → MonetaryAmount with numbers
- `_compile_lifecycle(project_uid: str) -> list[dict]` — read events table → Event array

The compiler is deterministic — same input always produces same output. No inference, no external calls. It just structures what's already in the flat fields.

### 3. Event emission in write paths

**File:** `autohelper/modules/bfa_todo/service.py` (MODIFY)

Wrap existing write functions to detect and record changes:

- `update_project()` — before writing, load current schema. After writing, compile new schema. Diff → emit events.
- `update_project_section()` — same pattern for section-level changes.
- `upsert()` (via repo) — compile schema_json on every write.

Pattern:
```python
def update_project(uid, changes):
    entry = repo.get(uid)
    old_schema = json.loads(entry.get("schema_json") or "{}")

    # ... existing update logic ...

    repo.upsert(entry, allow_curated=True)

    new_schema = compile_project_schema(entry)
    entry["schema_json"] = json.dumps(new_schema)
    # persist schema_json separately (lightweight update)

    changes = diff_schemas(old_schema, new_schema)
    if changes:
        emit_events_from_diff(uid, changes, source="manual")
```

### 4. Backfill existing entries

**File:** `scripts/bfa_schema_backfill.py` (NEW)

One-time script to compile schema_json for all existing bfa_projects entries:

```
python scripts/bfa_schema_backfill.py          # compile all
python scripts/bfa_schema_backfill.py --uid X   # compile one
python scripts/bfa_schema_backfill.py --dry-run  # show what would be compiled
```

Also seeds initial lifecycle events from available data:
- Entries with `source: "gdocs"` get a `created` event dated to their `created_at`
- Entries with `source: "staged"` get a `created` event + `reinitiated` event
- Entries with `status: "on_hold"` get an `on_hold` event

### 5. Schema utility script

**File:** `scripts/bfa_schema.py` (NEW)

```
python scripts/bfa_schema.py dump UID           # pretty-print JSON-LD for a project
python scripts/bfa_schema.py validate UID       # check schema consistency
python scripts/bfa_schema.py validate --all     # validate all projects
python scripts/bfa_schema.py diff UID           # show what changed since last compile
python scripts/bfa_schema.py events UID         # list lifecycle events for a project
python scripts/bfa_schema.py events --recent    # recent events across all projects
python scripts/bfa_schema.py stats              # schema coverage: how many projects have schema_json
```

### 6. Tests

**File:** `tests/test_schema.py` (NEW)

- `TestCompileSchema` — flat fields → JSON-LD structure, all types present, @id format correct
- `TestCompileBudget` — string "$1,565,703" → { value: 1565703 }, "$TBC" → null, phased breakdown
- `TestCompileContacts` — contacts section HTML → Person entities with roles
- `TestDiffSchemas` — detect phase change, contact change, budget change, name change
- `TestEventEmission` — diff produces correct event_type, previous_value, new_value
- `TestValidateSchema` — missing @id, orphaned references, budget mismatch all flagged
- `TestRoundTrip` — compile → serialize → deserialize → recompile = identical
- `TestBackfill` — existing entries get valid schema after backfill

## Files

| File | Action | Purpose |
|------|--------|---------|
| `autohelper/db/migrations/0018_project_events_and_schema.sql` | New | Events table + schema_json column |
| `autohelper/modules/bfa_todo/schema.py` | New | Compile, diff, emit, validate |
| `autohelper/modules/bfa_todo/service.py` | Modify | Event emission in write paths |
| `autohelper/modules/bfa_todo/pipeline/repo.py` | Modify | Compile schema_json on upsert |
| `scripts/bfa_schema_backfill.py` | New | One-time backfill |
| `scripts/bfa_schema.py` | New | Utility: dump/validate/diff/events |
| `tests/test_schema.py` | New | Schema compilation + diff + validation tests |

## Verification

1. Run migration → `bfa_project_events` table exists, `schema_json` column on `bfa_projects`
2. Run backfill → all 147 projects have `schema_json`, validate reports zero errors
3. Starlight entry has: Organization (Starlight Developments), Person (Nicholas Kasidoulis with role), MonetaryAmount (phased budget), lifecycle events (created, on_hold, reinitiated)
4. Edit a project via hub → event emitted, schema_json updated, `bfa_schema.py events UID` shows the change
5. All existing tests still pass (zero breaking changes)
6. New schema tests pass
