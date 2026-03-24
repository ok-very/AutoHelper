# JSON-LD Schema Integration Roadmap

## Overview

Every data transition in AutoHelper re-infers structure that could be captured once and reused. JSON-LD schemas (schema.org vocabulary, extended for public art project management) become the canonical internal representation. Human-readable formats (docx, HTML, ClickUp, spreadsheets) are projections from the schema, not sources of truth.

The integration follows three tiers, each building on the last. Work is organized by sessions, not calendar — each session closes a specific seam while extending the schema lattice.

---

## Tier 1 — Capture alongside (no breaking changes)

**Goal:** Add structured schema capture to existing write paths. Nothing that reads flat fields breaks. The schema layer grows organically as we work.

### Session 1: Foundation scaffold

- Migration: `bfa_project_events` table for lifecycle event capture
- Migration: `schema_json TEXT` column on `bfa_projects`
- `_compile_schema()` function in service.py — runs on every upsert, builds JSON-LD from flat fields + sections + events
- Event emission in existing write paths (`update_project`, `update_project_section`, `upsert`)
- `scripts/bfa_schema.py` — dump/validate/diff JSON-LD for any project

**Schema types introduced:**
- `Project` (custom, extends schema:CreativeWork) — uid, name, client, phase, status
- `Organization` — client/developer entities
- `Person` — contacts with role bindings
- `MonetaryAmount` — budget as structured numbers alongside display strings
- `Event` — lifecycle transitions (on_hold, reinitiated, phase_change, contact_change, name_change)

**Seam closed:** Lifecycle tracking. Every state change gets a typed event record. "When did Starlight go on hold?" becomes a query.

### Session 2: ClickUp stage monitor + schema binding

- Wire stage monitor to read Starlight P1's 96 tasks from ClickUp list 901326508900
- Blocking activity translation writes `currentStage` + `blockingActivities` into `schema_json`
- `sync_from_clickup` emits `project_created`, `phase_change` events
- Alias trigger: project name change → `name_change` event + org `@id` binding
- Client alias resolution writes structured `Organization` entity to `schema_json` (not just a short string)
- Stage-to-phase mapping results cached in schema, not re-inferred on render

**Seam closed:** ClickUp → DB. Sync produces typed entities, not flat strings. Next agent session reads schema instead of re-querying ClickUp.

### Session 3: Docx round-trip with structural diff

- `docx_run_extractor` emits JSON-LD fragments (Person, Organization) alongside HTML during ingestion
- Structured diff engine: compare old `schema_json` to new extraction, identify typed changes
- Automatic lifecycle event emission from diffs (contact replaced, budget updated, phase advanced)
- Change report output: "2 contacts changed, 1 budget updated" — typed events, not text diffs
- PostToolUse hook: after any BFA edit, compile schema + diff + emit events

**Seam closed:** Docx edit → DB. Edits produce structural change records automatically. The round-trip captures what changed and why, not just the new text.

---

## Tier 2 — Structured fields (minor schema changes)

**Goal:** Replace string-encoded data with typed structures. Flat `fields_json` strings become structured objects. Associations gain temporal context.

### Session 4: Structured budget + phased allocation

- Budget fields change from `"$1,565,703"` (string) to `{ "value": 1565703, "currency": "CAD" }`
- Phase allocation array: `phases: [{ name, art, total, status }]`
- Display strings computed from numbers (not the other way around)
- ClickUp budget custom fields map directly to schema — no string parsing
- Validation: phase budgets sum to total, art ≤ total
- Migration + backfill existing entries from string parsing

**Seam closed:** Budget comparisons, aggregations, and validation work on numbers. "Total art budget across all active projects" is a SQL sum, not a string-parsing script.

### Session 5: Temporal contact associations

- `project_contact_associations` gains `effective_date`, `end_date`, `replaced_by_id`
- Contact changes become queryable: "who was the developer contact for Starlight before March 2026?"
- `contact_change` events reference the association IDs
- Hub surface shows contact timeline per project
- Artist associations get the same treatment (shortlisted_date, selected_date, deselected_date)

**Seam closed:** Contact/role history. "Nicholas replaced David Woo" is a typed relationship with dates, not prose in a notes field.

### Session 6: ClickUp staging as schema diffs

- `bfa_pending_changes` stores typed schema diffs, not HTML blobs
- ClickUp phase advance → pending change: `{ event_type: "phase_change", previous: "PPAP", new: "DPAP" }`
- Approval surface renders structured cards: field-level accept/reject
- Accepted changes merge into `schema_json` + emit lifecycle events
- Rejected changes logged with reason (also an event)

**Seam closed:** ClickUp staging → approval. PMs see structured diffs, not raw text. Accept/reject is per-field, not all-or-nothing.

---

## Tier 3 — Schema as canonical (architectural revision)

**Goal:** JSON-LD becomes the source of truth. All other representations are derived views.

### Session 7: Schema-first data layer

- `schema_json` becomes the primary column. `fields_json` is a computed view for backward compatibility
- Write paths accept JSON-LD directly
- `_compile_schema()` inverts: `_project_fields_from_schema()` derives flat fields for legacy reads
- Section HTML generated from schema + templates, not stored independently
- Test suite: round-trip `schema → flat → schema` preserves all data

### Session 8: Cross-module shared vocabulary

- Artists, projects, contacts, artworks share schema.org types with consistent `@id` references
- An artist in a BFA project and in the artist directory is one `Person` entity
- An organization (developer) referenced across multiple projects is one `Organization`
- The contacts hub becomes a JSON-LD entity store with projections to the SQL table
- Deduplication is structural (same `@id`), not heuristic (name matching)

### Session 9: Inference elimination

- All import paths (ClickUp, docx, Excel, email) emit JSON-LD as primary output
- Merge engine: two schemas from different sources → unified schema with conflict markers
- Agent hooks capture every structural inference and store it permanently
- Second-pass agents read schema, never re-infer from text
- Inference budget approaches zero for steady-state operations

---

## Agent hooks and harnesses

### Compile-on-write hook

Runs after every BFA edit (PostToolUse on Edit/Write to bfa_todo files):

1. Load current `schema_json` for affected project
2. Re-compile from flat fields + sections
3. Diff old vs new schema
4. Emit lifecycle events for any structural changes
5. Persist updated `schema_json`

### Inference capture pattern

When any agent (Claude Code, scheduled sync, future automation) parses unstructured text:

```python
# Instead of just:
fields["client"] = "Starlight"

# Also emit:
schema["client"] = {
    "@type": "Organization",
    "@id": f"bfa:org-{generate_id('org')}",
    "name": "Starlight Developments",
    "alternateName": ["Starlight Investments", "Starlight"],
}
emit_event("alias_resolved", {
    "input": "Starlight - Lougheed Village P1",
    "resolved_org": schema["client"]["@id"],
    "method": "name_prefix_parse",
})
```

The inference method is recorded. If it was wrong, the correction also gets recorded. The alias table becomes a log of resolutions, not just a lookup.

### Schema validation harness

`scripts/bfa_schema.py validate` checks:
- All `@id` references resolve to existing entities
- Budget phases sum to total
- Contact associations have valid Person references
- Lifecycle events are chronologically ordered
- No orphaned Organization entities

Run as part of test suite — schema consistency is a regression test.

---

## Vocabulary reference

| Domain concept | schema.org type | Custom extensions |
|---|---|---|
| BFA project | CreativeWork | `projectPhase`, `blockingActivities`, `projectLifecycle` |
| Developer/client | Organization | `alternateName` for aliases |
| Contact person | Person | — |
| Contact role | Role | `replaces`, `effectiveDate`, `endDate` |
| Budget | MonetaryAmount | `phasedAllocation` array |
| Project location | Place + PostalAddress | `municipality` (for policy lookup) |
| Lifecycle event | Event | `eventType`, `previousValue`, `newValue`, `source` |
| Artwork | VisualArtwork | `installDate`, `fabricationStatus` |
| Artist | Person | `artistPractice`, `portfolio` |
| Template stage | Action | `stage`, `dependsOn`, `completedDate` |

---

## Success criteria

- **Tier 1 complete:** Every project upsert produces valid JSON-LD. Lifecycle events capture all state transitions. Agents read schema before re-inferring.
- **Tier 2 complete:** Budgets are numbers, contacts have temporal context, ClickUp staging shows typed diffs. Zero string parsing for structured data.
- **Tier 3 complete:** Schema is canonical. Import/export/sync are projections. Inference cost for steady-state operations approaches zero. An artist, contact, or organization referenced across modules is one entity with one `@id`.
