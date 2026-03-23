# AutoHelper

Local desktop service for public art project management. Python FastAPI backend (port 8100) + React UI served as static files.

## Architecture

- **autohelper/** — Python FastAPI service. SQLite database, filesystem indexing, OAuth integrations (ClickUp, Google, Monday), document generation, mail polling.
- **ui/** — React multi-page app (Vite). Builds to `autohelper/gui/artists-dist/` as static files served by the Python service via `dashboard_router.py`.
- **desktop/** — Electron tray app. Manages autohelper process lifecycle on Windows.

## Dev Workflow

**NEVER spawn server processes from the Bash tool.** No uvicorn, no `mise run`, no background servers. The user manages servers in their own terminal.

### mise (task runner + tool manager)
- Config: `mise.toml` at repo root
- Manages: Python 3.13, Node 24, venv activation, `.env` loading
- `mise run dev` — start dev server (port 8100, `--reload`, `--factory`)
- `mise run venv` — create/update venv with editable install
- `mise run validate` — test ClickUp connection
- `mise run ui:build` — build UI into autohelper/gui/artists-dist
- `mise run ui:dev` — watch mode for UI

### App entry point
- `autohelper.app:build_app` with `--factory` flag
- Editable install required: `pip install -e .`
- `--reload` is the default — NEVER tell the user to restart the server

### Kill scripts
- Windows: `scripts/kill-dev.ps1`
- Bash: `scripts/kill.sh`

### Secrets & dotenvx
- **`.env`** — non-secret config (client IDs, redirect URIs, server settings)
- **`.env.agent`** — encrypted API tokens via dotenvx
- **To read a secret:** `dotenvx get CLICKUP_API_TOKEN -f .env.agent`
- **To use in a command:** pass via env var, NEVER hardcode tokens
- **To add/update:** `dotenvx set CLICKUP_API_TOKEN "pk_..." -f .env.agent`

### Testing changes
- `--reload` auto-reloads on save
- Verify without server: `python -c "from autohelper.app import build_app; build_app()"`
- Browser-testable endpoints should be GET, not POST

## UI Development

### Component system
- Atoms in `ui/src/ui/atoms/` — Badge, Button, Card, Checkbox, FilterChip, Inline, Label, ProgressBar, Select, Spinner, Stack, RadioGroup, TextInput
- Theme tokens in `ui/src/ui/theme/variables.css` — `--ws-*` CSS custom properties
- **`Text` component does NOT exist here** — use raw `<span>`/`<p>`/`<h2>` with `text-ws-fg`, `text-ws-text-secondary`, etc.

### Reference page
- `ProjectDetailPage` is the reference for patterns: `max-w-3xl` content column, Cards for discrete data sections, raw elements with `--ws-*` classes

### DESIGN.md rules
- Read `docs/DESIGN.md` BEFORE writing UI code
- "No cards unless data is ephemeral"
- "Declarative, not encouraging" — no marketing copy
- "Left-aligned everything"
- "No color for decoration alone"

## Data Ownership Model

Every data record in AutoHelper has an ownership class. **Before writing any code that mutates data, identify the class and respect it.**

| Class | Authority | Overwritable? | Flag |
|-------|-----------|---------------|------|
| **input** | External system (ClickUp, Excel, user form) | Yes, by re-sync | `ownership` absent or `"input"` |
| **curated** | Human-edited, imported from authoritative source (e.g. Google Docs preambles) | NO — only by explicit re-import from authority | `fields["ownership"] = "curated"` |
| **generated** | System pipeline output (rendered HTML, .docx, GDocs payloads) | Yes, always safe to regenerate | Not stored in DB — these are filesystem artifacts |

### Enforcement
- `CuratedContentError` in `pipeline/repo.py` — raised when `upsert()` or `update_section()` would overwrite a curated entry without `allow_curated=True`
- `upsert_batch()` silently skips curated entries (logs warning) to avoid breaking batch operations
- Router returns **409 Conflict** when curated guard fires

### Checklist for new data flows
1. Trace the path: source → transform → persist → render
2. Label each stage's ownership class
3. If a new record type lacks an ownership flag, add one
4. Every write boundary must check ownership before mutating
5. Only the authoritative source path passes `allow_curated=True`

## Module Layout

- `modules/felt/` — Felt interactive map API
- `modules/documents/context_map/` — static context map production
- `modules/clickup/` — ClickUp integration
- `modules/projects/` — project management
- `modules/bfa_todo/` — BFA task tracking
- `shared/geo/` — geocoder, Overpass POIs, public art GeoJSON
- `shared/ids.py` — ID generation
