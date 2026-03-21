# Document Generation Pipeline

End-to-end pipeline: contacts + project context → templated .docx → PDF → ClickUp attachment.

## Architecture

```
Project (intake + city overlay)
    ↓
Contact Hub (resolve_merge_fields → per-role contacts)
    ↓
build_project_context() → merged dict
    ↓
render_template() → versioned .docx
    ↓
convert_to_pdf() → .pdf via Word COM (docx2pdf)
    ↓
cu.attachments.upload() → ClickUp task attachment
```

## Key Files

| File | Purpose |
|------|---------|
| `modules/documents/docx_engine.py` | Template discovery, rendering, PDF conversion, context building |
| `modules/documents/router.py` | HTTP endpoints (`/api/documents/docx/*`) |
| `modules/contacts/hub.py` | Contact CRUD, project associations, `resolve_merge_fields()` |
| `modules/projects/service.py` | Project creation, ClickUp provisioning with Stage dropdown |
| `modules/projects/stage_monitor.py` | Live stage status from ClickUp (name-matching, not field-dependent) |
| `modules/clickup/client.py` | ClickUp API client with `AttachmentsAPI` for file uploads |

## Templates

Three legal letter templates in OneDrive `_bfa/templates/`:

### artwork_acceptance.docx (14 fields)
artist_address_line1, artist_address_line2, artist_email, artist_name, artwork_title, developer_address_line1, developer_address_line2, developer_contact_name, developer_contact_title, developer_name, developer_phone, generated_at, install_date, site_address

### transfer_of_title.docx (14 fields)
agreement_date, agreement_section, artist_address_line1, artist_address_line2, artist_country, artist_name, artwork_title, developer_address_line1, developer_address_line2, developer_name, developer_phone, development_name, generated_at, site_address

### statutory_declaration.docx (11 fields)
artwork_title, city_name, declarant_address, declarant_name, declarant_title, declaration_city, declaration_date, developer_name, final_report_author, generated_at, registration_type

## Context Resolution

`build_project_context(project_id)` merges data from two sources:

### From project intake
- `project_name`, `artwork_title`, `development_name` (all from intake.project_name)
- `developer_name` (from intake.developer_name)
- `site_address` (civic_address + municipality)
- `neighbourhood`
- `city_name` (from city overlay)

### From contact hub (`resolve_merge_fields`)
- `developer_contact_name`, `developer_name` (from "developer" role contact)
- `developer_email`, `developer_phone`, `developer_contact_title`
- `artist_name`, `artist_email` (from "artist" role contact)
- `city_contact_name` (from "city_planner" role)
- `coordinator_name`, `engineer_name`, `architect_name`, `landscape_architect_name`

### Auto-generated
- `generated_at` — render timestamp in footer
- `filename` — versioned filename

Unfilled fields render as `[field_name]` placeholders in the document.

## Endpoints

### `GET /api/documents/docx/templates`
List available templates with merge field names.

### `GET /api/documents/docx/templates/{key}`
Single template metadata.

### `POST /api/documents/docx/render`
Render a .docx template. Returns FileResponse (download).
```json
{"template_key": "artwork_acceptance", "project_id": "proj_...", "context": {}}
```

### `POST /api/documents/docx/pipeline`
Full pipeline: render → PDF → optional ClickUp attachment.
```json
{
  "template_key": "artwork_acceptance",
  "project_id": "proj_...",
  "clickup_task_id": "86agbgth7",
  "context": {}
}
```
Returns metadata with `docx_path`, `pdf_path`, `unfilled`, and `attachment` (if task_id provided).

## ClickUp Provisioning

`provision_project(project_id)` in `service.py`:

1. Creates a folderless list in space (or list in folder if folder_id configured)
2. Creates a "Stage" dropdown custom field with 11 BFA stage options
3. Creates all tasks (parents first, then children) with policy guidance in description
4. Sets Stage value on each task (requires sufficient ClickUp plan tier — currently blocked by FIELD_033)
5. Wires task dependencies
6. Stores `clickup_list_id`, `clickup_stage_field_id` on project record

### Workspace config (.env)
- `CLICKUP_WORKSPACE_ID=90132092939` (BFA workspace)
- `CLICKUP_SPACE_ID=90138845441` (Public Art Projects space)
- `CLICKUP_FOLDER_ID` — optional, uses space-level list creation if empty

### Stage nomenclature
"Stage" is the domain term used externally and in ClickUp. Previously called "phase" internally — renamed to "stage" throughout.

## Test Project: Keltic Sussex

- Project ID: `proj_02ef151e9226`
- Address: 6620 Sussex Avenue, Burnaby (Metrotown)
- Developer: Keltic Canada Development Corp.
- City overlay: burnaby (City of Burnaby, 1% contribution rate)
- ClickUp list: `901326508227`
- Stage field: `eb916dcb-31ff-41fd-bd14-ac6266387b0c`
- 117 resolved tasks from Burnaby template across 11 stages

### Contact associations
- Developer: Keltic Canada Development (con_44eaa1dd0f40)
- Artist: not yet associated
- Other roles: not yet associated

## Dependencies

- `docxtpl>=0.18.0` — Jinja2 template rendering inside .docx
- `docx2pdf>=0.1.8` — DOCX→PDF via Word COM automation (Windows only)
- `httpx` — async HTTP for ClickUp API

## Legal Letters UI Module

Accessible at `/legal-letters`. Registered in `moduleRegistry.ts` as `legal-letters`.

- Project selector (provisioned projects only)
- Template table: artwork_acceptance, transfer_of_title, statutory_declaration
- Per-template: filled/total fields count, pending badge, Generate PDF button
- Expandable field detail: field name (mono), value or PENDING
- Generation results inline: filename, timestamp, ClickUp attachment status, subtask count

### Backend endpoints
- `GET /api/documents/docx/preview/{project_id}/{template_key}` — field status without rendering
- `POST /api/documents/docx/pipeline` — render → PDF → auto-attach to ClickUp task → create subtasks for unfilled fields

### ClickUp integration
Legal letter tasks are mapped by temp_id:
- artwork_acceptance → dry-11-3 (Execute Letter of Acceptance)
- transfer_of_title → dry-11-4 (Execute Transfer of Title)
- statutory_declaration → dry-11-5 (Execute Statutory Declaration)

The pipeline auto-resolves the ClickUp task ID by matching task name on the provisioned list. Subtasks are created as "Resolve: {Field Name}" with tag `pending_merge_field`.

## Contact Data

### Master CSV import
7,450 contacts imported from `7. Accounting & Operations/BFA Contacts/final_7450_full.csv` (Outlook export format). Column mapping added for `E-mail Address`, `Business Phone`, etc.

### Artist auto-resolution
`build_project_context()` searches the artist directory by project name in `engagement.public_art_projects`. If found, creates a hub contact and associates with the project as role="artist".

### Keltic Sussex contacts
- **Developer**: Keltic Canada Development Corp. (info@kelticdevelopment.com) — address: 2338 Park Place, 666 Burrard St, Vancouver BC V6C 2X8
- **Artist**: Thomas Cannell (cannellcreative@shaw.ca, 604-833-0393) — address: 4164 Jericho Drive, Vancouver BC V6N 0A4
- **Artwork**: Sacred Belongings (8 sculptures — 4 bentwood boxes + 4 basalt benches, Coast Salish designs)

## Known Limitations

- **ClickUp plan limit**: Stage dropdown values can't be set on tasks (FIELD_033). Stage monitor works via name matching instead. Will resolve when plan is upgraded.
- **PDF conversion requires Word**: Uses `win32com.client` Word COM directly (not docx2pdf wrapper). Not available on Linux/macOS without LibreOffice alternative.
- **Template directory**: Hardcoded OneDrive path. Templates must be accessible at `PA PROCEDURES/_bfa/templates/`.

## Address Fields (Migration 0015)

Added to `contacts` table: `street_address`, `city`, `state`, `postal_code`, `country`.

- Hub CRUD (`create_contact`, `update_contact`) accepts address fields
- CSV import maps Outlook export columns (`Business Street`, `Business City`, etc.)
- `build_project_context()` maps `{role}_address_line1` (street), `{role}_address_line2` (city, state postal), `{role}_country`

## Output Path

Legal letters save to the project's OneDrive folder:
```
1. PUBLIC ART/ALL PROJECTS/{project_folder}/Final Documentation/Legal Letters/
```

Project folder detection: `find_project_folder(project_name)` searches `ALL PROJECTS/` for a folder whose name contains all tokens of the project name.

Falls back to `data_dir()/documents/legal_letters/` if OneDrive folder not found.

## Close-out Fields (PM-editable)

Stored on `ProjectRecord`, editable via `PUT /api/projects/{id}/legal-fields`:

- `legal_address` — Land title description (Lot/Block/Plan)
- `install_date`, `agreement_date`, `agreement_section`
- `declarant_name`, `declarant_title`, `declarant_address`
- `declaration_city`, `declaration_date`
- `final_report_author`, `registration_type`, `registration_number`

## Municipality → Legal Letters

Driven by city close-out checklists. Defined in `MUNICIPALITY_LEGAL_LETTERS` in `router.py`.

- **Vancouver**: artwork_acceptance + transfer_of_title + statutory_declaration (Section 219 covenant + Section 5.0)
- **Burnaby**: all three (Section 5.0 Security Release Checklist requires all for LC release)
- **Default**: all three until city checklist says otherwise

## ClickUp Structure

- Each project gets its own **folder** in Public Art Projects space
- Lists inside folders, hyphenated naming: `Developer - Address`
- Phased projects: one folder per development, one list per phase (e.g., "Starlight - Lougheed Village" folder → "Starlight - Lougheed Village P1" list)

## Provisioned Projects

| Project | ID | Municipality | Artwork | Artist | ClickUp Folder |
|---|---|---|---|---|---|
| Keltic - 6620 Sussex | proj_02ef151e9226 | Burnaby | Sacred Belongings | Thomas Cannell | 901317851134 |
| Intracorp - 2025 Arbutus | proj_aa573d81308f | Vancouver | Woodland Reflections | Christian Huizenga | 901317851135 |
| Starlight - Lougheed Village P1 | proj_347c8cf3abf0 | Burnaby | — | — | 901317851128 |

## Running for a New Project

1. Create project with intake (municipality, project_name, developer_name, artwork_title, civic_address)
2. Associate contacts from hub (developer contact + artist)
3. Provision to ClickUp (creates folder + list with task hierarchy + Stage field)
4. Run pipeline: renders applicable legal letters per municipality, converts to PDF, saves to OneDrive `Final Documentation/Legal Letters/`, attaches to ClickUp, creates subtasks for PENDING fields
5. PM fills close-out fields via `PUT /api/projects/{id}/legal-fields` as project progresses
