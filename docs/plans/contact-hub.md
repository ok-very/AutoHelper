# Contact Hub — Central Resolution Layer with Bidirectional Sync

## Status: Session A in progress

### Completed
- [x] DB migration: `contacts` + `project_contact_associations` tables (0014)
- [x] Hub service: CRUD, search, association management, resolution (`hub.py`)
- [x] CSV import pipeline (`import_csv.py`)
- [x] Router: 18 endpoints (hub CRUD, associations, import, resolution)
- [x] API client: hub search, CRUD, associations, resolution endpoints
- [ ] ContactsPage UI: table view, search, category filter, detail view
- [ ] ProjectDetailPage: team section showing associated contacts

### Session B (pending)
- [ ] Update `compose_email()` to resolve contacts from hub
- [ ] Update mail sender matching to use hub
- [ ] Enrich auto-triage with contact associations
- [ ] Mail detail view: sender contact card with project associations
- [ ] Quick-add contact association from mail view

### Session C (pending)
- [ ] ClickUp → Hub: extract contacts from task custom fields during stage polling
- [ ] Hub → ClickUp: push contact updates to task custom fields
- [ ] Exchange → Hub: pull contacts from Outlook
- [ ] Hub → Exchange: push new/updated contacts to Outlook
- [ ] Sync status indicators in the contacts UI

## Architecture

### Data Model

**contacts** — canonical contact record in SQLite:
- id, first_name, last_name, full_name, company, job_title
- email_primary (unique), email_secondary
- phone_business, phone_mobile
- category (from 85 canonical categories)
- notes, confidence (HIGH/MEDIUM/LOW), staleness_label (Active/Aging/Dormant)
- exchange_id, clickup_contact_ref (sync identifiers)
- source (import/exchange/clickup/manual), created_at, updated_at

**project_contact_associations** — links contacts to projects with a role:
- id, contact_id (FK), project_id, role, is_primary, notes, created_at
- Roles: developer, city_planner, artist, panel_member, architect, landscape_architect, community_advisor, indigenous_advisor, project_coordinator, engineer, other

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /contacts/hub | Search contacts (q, category, staleness, pagination) |
| GET | /contacts/hub/categories | Distinct categories with counts |
| GET | /contacts/hub/count | Total contact count |
| GET | /contacts/hub/{id} | Get contact with associations |
| POST | /contacts/hub | Create contact |
| PUT | /contacts/hub/{id} | Update contact |
| DELETE | /contacts/hub/{id} | Delete contact |
| POST | /contacts/hub/import | Import from CSV (background) |
| GET | /contacts/projects/{id}/contacts | Project's contacts by role |
| POST | /contacts/projects/{id}/contacts | Associate contact with project |
| DELETE | /contacts/associations/{id} | Remove association |
| GET | /contacts/resolve/sender?email= | Resolve sender for mail triage |
| GET | /contacts/resolve/project/{id}/merge-fields | Template merge fields |

### Key Files

| File | Purpose |
|------|---------|
| `autohelper/db/migrations/0014_contacts_hub.sql` | Schema |
| `autohelper/modules/contacts/hub.py` | Hub service (CRUD, search, resolution) |
| `autohelper/modules/contacts/import_csv.py` | CSV import pipeline |
| `autohelper/modules/contacts/router.py` | All endpoints |
| `ui/src/lib/api.ts` | Frontend API client |

### Seed Data
- `E:\scratch\BFA-Contacts-output\final_master_contacts.csv` — 9,068 contacts
- `E:\scratch\BFA-Contacts-output\resolved_contacts.csv` — 417 manual reconciliations
