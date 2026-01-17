# AutoHelper

Local-first Python filesystem orchestration service for AutoArt integration.

## Features

- **Path Safety**: Root allowlist, canonicalization, symlink blocking
- **SQLite Index**: WAL mode, FTS5 search, migration system
- **Audit Logging**: Append-only log with idempotency support
- **FastAPI**: Health/status endpoints, request context tracing

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Set environment variables
export AUTOHELPER_ALLOWED_ROOTS="C:\\Projects,D:\\Data"
export AUTOHELPER_DB_PATH="./data/autohelper.db"

# Run the server
python -m autohelper.main

# Or use uvicorn directly
uvicorn autohelper.app:build_app --factory --reload
```

## API Endpoints

### Health
- `GET /health` - Simple health check
- `GET /status` - Detailed status with DB, migrations, roots

### Index (M1)
- `POST /index/rebuild` - Full index rebuild
- `POST /index/rescan` - Incremental rescan
- `GET /index/status` - Index run status

### Search (M2)
- `GET /search` - Search files by path/name/content

### References (M3)
- `POST /reference/register` - Register file reference
- `POST /reference/resolve` - Resolve references

## Configuration

Environment variables (prefix `AUTOHELPER_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | 127.0.0.1 | Server host |
| `PORT` | 8100 | Server port |
| `DB_PATH` | ./data/autohelper.db | SQLite database path |
| `ALLOWED_ROOTS` | (empty) | Comma-separated root paths |
| `BLOCK_SYMLINKS` | true | Block symlink traversal |
| `LOG_LEVEL` | INFO | Logging level |
| `CORS_ORIGINS` | localhost:5173,localhost:3000 | CORS origins |

## Project Structure

```
autohelper/
├── app.py              # FastAPI app factory
├── main.py             # Uvicorn entrypoint
├── config/             # Settings (pydantic-settings)
├── shared/             # Types, errors, logging (shared across modules)
├── infra/
│   ├── fs/             # Filesystem protocols, path safety
│   └── audit/          # Audit logging
├── db/
│   ├── conn.py         # SQLite connection
│   ├── migrate.py      # Migration runner
│   └── migrations/     # SQL migration files
└── modules/
    ├── health/         # Health/status endpoints
    ├── index/          # Indexer (M1)
    ├── search/         # Search (M2)
    └── ...
```

## Integration

AutoArt calls AutoHelper for filesystem operations. AutoHelper treats `work_item_id` and `context_id` as opaque IDs from AutoArt.

Headers for tracing:
- `X-Request-ID` - Request identifier
- `X-Work-Item-ID` - AutoArt work item
- `X-Context-ID` - AutoArt context
- `X-Idempotency-Key` - Idempotency key for retries
