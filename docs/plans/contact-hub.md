# Contact Hub — Central Resolution Layer with Bidirectional Sync

## Status: Session A complete, Session B/C pending

### Session A (complete)
- [x] DB migration: `contacts` + `project_contact_associations` tables (0014, 0015 address fields)
- [x] Hub service: CRUD, search, association management, resolution (`hub.py`)
- [x] Canonical contact slots with role aliases for backward compat
- [x] CSV import pipeline with Outlook export format support (`import_csv.py`)
- [x] Router: hub CRUD, associations, import, resolution, Exchange session endpoints
- [x] API client: hub search, CRUD, associations, resolution endpoints
- [x] ContactsPage UI: table with search, category/staleness filters, pagination, expandable detail rows
- [x] ProjectDetailPage: TeamCard showing contacts by role
- [x] Hub → Exchange sync queue (`queue_for_exchange_sync`)
- [x] Persistent Exchange session with MFA (`exchange_session.ps1`)

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

### Contact Slots

Canonical slots defined in `hub.py:CONTACT_SLOTS`:
- **Team:** contact, owner, architect, landscape
- **Stage contacts:** ppap, dpap, eoi
- **Selection:** sp1, ao, sp2, selection_panel
- **Artists:** shortlisted_artist, selected_artist
- **Advisory:** community_advisory, indigenous_advisor
- **Generic:** project_coordinator, engineer, city_planner, other

Legacy role aliases map to canonical slots (e.g. `developer` → `contact`).

### Data Model

**contacts** table (0014 + 0015):
- id, first_name, last_name, full_name, company, job_title
- email_primary (unique), email_secondary
- phone_business, phone_mobile
- street_address, city, state, postal_code, country
- category, notes, confidence, staleness_label, last_seen
- exchange_id, clickup_contact_ref
- source (import/exchange/clickup/manual), created_at, updated_at

**project_contact_associations** table:
- id, contact_id (FK), project_id, role (canonical slot), is_primary, notes, created_at

### Key Files

| File | Purpose |
|------|---------|
| `autohelper/db/migrations/0014_contacts_hub.sql` | Core schema |
| `autohelper/db/migrations/0015_contacts_address.sql` | Address columns |
| `autohelper/modules/contacts/hub.py` | Hub service, slots, resolution |
| `autohelper/modules/contacts/import_csv.py` | CSV import pipeline |
| `autohelper/modules/contacts/router.py` | All endpoints |
| `autohelper/modules/contacts/exchange_sync.py` | Exchange session + sync |
| `autohelper/modules/contacts/powershell/exchange_session.ps1` | Persistent PS session |
| `ui/src/pages/contacts/ContactsPage.tsx` | Contacts table UI |
| `ui/src/pages/projects/ProjectDetailPage.tsx` | TeamCard component |
| `ui/src/lib/api.ts` | Frontend API client |
