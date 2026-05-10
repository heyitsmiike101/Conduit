# Conduit Developer Documentation

This document is the source of truth for developers working on the Conduit codebase. It covers architecture, setup, key concepts, and workflows. **Update this file whenever you make significant changes to the system.**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Tech Stack](#tech-stack)
4. [Development Setup](#development-setup)
5. [Key Concepts](#key-concepts)
6. [Database & Models](#database--models)
7. [Backend API](#backend-api)
8. [Frontend](#frontend)
9. [Scripts & Supporting Tools](#scripts--supporting-tools)
10. [Common Workflows](#common-workflows)
11. [Important Implementation Details](#important-implementation-details)

---

## Architecture Overview

Conduit is a script-hosting platform that:

- **Manages Python scripts** on disk with version history tracking
- **Schedules scripts** via cron expressions with APScheduler
- **Executes scripts** in a queue with concurrency control (default: single-instance per script)
- **Injects config** (Variables/API Keys) into each run securely
- **Shares data** between scripts via InfoTables
- **Provides import-able tools** — reusable Python modules available to all scripts
- **Tracks execution history** with stdout/stderr/API call logging
- **Enforces permissions** (read/write/create tables) per script via ScriptPermission rows

### High-Level Flow

```
User (UI)
  ↓
FastAPI Backend (port 8000)
  ├─ REST API → SQLAlchemy ORM → SQLite DB
  ├─ Runner Service → subprocess runner + queue
  ├─ Scheduler Service (APScheduler) → triggers cron jobs
  ├─ Config Injector Service → writes temp config files
  └─ Encryption Service → encrypts secrets at rest
  ↓
Python Scripts (on disk)
  ├─ Main scripts: data/scripts/{global,accounts}/{id}/script.py
  └─ Tools: data/tools/{id}/{python_name}.py
  ↓
conduit-helper library (in each script)
  └─ get_config() → reads injected config
  └─ get_table() → reads/writes InfoTable rows
  └─ log_api_call() → posts to internal API
  └─ run_script() → triggers another script
```

---

## Project Structure

```
Conduit/
├── backend/                       # FastAPI application
│   ├── app/
│   │   ├── main.py               # App entrypoint, lifespan hooks
│   │   ├── api/                  # Route handlers
│   │   │   ├── scripts.py        # Script CRUD + file browser + content
│   │   │   ├── cron_jobs.py      # Schedule management
│   │   │   ├── executions.py     # Run history + logs
│   │   │   ├── variables.py      # Secrets + config
│   │   │   ├── tables.py         # InfoTable CRUD
│   │   │   ├── internal.py       # Endpoints called by running scripts
│   │   │   └── ...
│   │   ├── db/
│   │   │   ├── models.py         # SQLAlchemy ORM definitions
│   │   │   ├── session.py        # Database session factory
│   │   │   └── __init__.py       # init_db()
│   │   ├── schemas/              # Pydantic request/response models
│   │   ├── services/             # Business logic
│   │   │   ├── runner_service.py # Subprocess execution + queuing
│   │   │   ├── scheduler_service.py # Cron job scheduling
│   │   │   ├── config_injector_service.py # Config file writing
│   │   │   ├── encryption_service.py # Secret encryption/decryption
│   │   │   └── ...
│   │   └── core/
│   │       ├── config.py         # Settings (env vars)
│   │       ├── logging.py        # Logging configuration
│   │       └── security.py       # Future auth/RBAC
│   ├── tests/                    # (currently minimal)
│   └── requirements.txt          # Python dependencies
│
├── frontend/                      # React + Vite application
│   ├── src/
│   │   ├── main.jsx              # Entry point
│   │   ├── App.jsx               # Route definitions
│   │   ├── api/                  # API client functions
│   │   │   ├── client.js         # Base HTTP client
│   │   │   ├── scripts.js        # Script endpoints
│   │   │   ├── cronJobs.js       # Schedule endpoints
│   │   │   └── ...
│   │   ├── pages/                # React page components
│   │   │   ├── Scripts.jsx       # Script list + create
│   │   │   ├── ScriptDetail.jsx  # Editor (main file + file browser)
│   │   │   ├── Tools.jsx         # Tool list + create (NEW)
│   │   │   ├── CronJobs.jsx      # Schedule list + create
│   │   │   ├── Executions.jsx    # Execution history
│   │   │   ├── Dashboard.jsx     # Overview + metrics
│   │   │   ├── Docs.jsx          # In-app documentation
│   │   │   └── ...
│   │   ├── components/           # Reusable UI components
│   │   ├── hooks/                # Custom React hooks
│   │   └── context/              # React Context (account selector)
│   ├── dist/                     # Built output (gitignored)
│   └── package.json              # Node dependencies
│
├── helper/                        # conduit-helper Python package
│   ├── conduit/
│   │   ├── __init__.py           # Exports get_config, get_table, log_api_call
│   │   ├── config.py             # get_config() implementation
│   │   ├── tables.py             # get_table() implementation
│   │   ├── logging.py            # log_api_call() implementation
│   │   └── runner.py             # Dev mode runner
│   └── setup.py                  # Package metadata
│
├── data/                          # Runtime data (gitignored in production)
│   ├── scripts/
│   │   ├── global/               # Global-scope scripts
│   │   │   └── {script-id}/
│   │   │       ├── script.py     # Main entry point
│   │   │       └── ...           # Supporting files
│   │   └── accounts/             # Account-scoped scripts
│   │       └── {account-id}/
│   │           └── {script-id}/
│   ├── tools/                    # Supporting tool modules (NEW)
│   │   └── {tool-id}/
│   │       ├── {python_name}.py  # Main importable file
│   │       └── ...               # Supporting files
│   ├── conduit.db                # SQLite database
│   ├── .secret_key               # Fernet encryption key (gitignored)
│   └── queue_state.json          # Persisted execution queue (optional)
│
├── examples/                      # Example scripts
│   ├── 01_hello_world/
│   ├── 02_using_config/
│   ├── 03_reading_tables/
│   ├── 04_writing_tables/
│   └── 05_api_logging/
│
├── instructions.md               # Architecture specification
├── BUILD_PLAN.md                # Build checklist (for feature completeness)
└── developer_documentation.md    # THIS FILE
```

---

## Tech Stack

| Layer | Tech | Notes |
|-------|------|-------|
| **Frontend** | React 18, Vite, Tailwind, React Query, Monaco Editor, date-fns | SPA, single-account mode for now |
| **Backend** | FastAPI, Python 3.9+, SQLAlchemy, APScheduler, Pydantic | Async runtime for subprocess handling |
| **Database** | SQLite | 15 tables, no migrations (uses `create_all`) |
| **Encryption** | cryptography (Fernet) | Secrets encrypted at rest |
| **Helper** | Pure Python, no external deps (dev mode reads fixtures) | Installed as editable package |

---

## Development Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- Git

### First-time setup

```bash
# 1. Clone and cd
git clone <repo>
cd Conduit

# 2. Backend: create venv and install
cd backend
python3 -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt

# 3. Install conduit-helper in editable mode (for development)
cd ../helper
pip install -e .

# 4. Frontend: install dependencies
cd ../frontend
npm install

# 5. Start backend (port 8000)
cd ../backend
uvicorn app.main:app --reload --port 8000

# 6. In another terminal, start frontend (port 5173)
cd frontend
npm run dev
```

### Configuration

**Backend**: Edit `backend/app/core/config.py` or set env vars:
- `DATA_DIR` — root data folder (default: `data/`)
- `DATABASE_URL` — SQLite path (default: `data/conduit.db`)
- `SECRET_KEY_FILE` — encryption key file (default: `data/.secret_key`)
- `LOG_LEVEL` — logging level (default: `INFO`)
- `CORS_ALLOWED_ORIGINS` — comma-separated origins (default: `*`)
- `MAX_CONCURRENT_SCRIPTS` — concurrency limit (default: 1)

**Frontend**: Edit `frontend/.env` or `vite.config.js` to change API base URL (default: `/api/v1`).

---

## Key Concepts

### Scripts

**Regular Scripts** (`script_type = "script"`)
- Owned by a user (global or account scope)
- Entry point: always `script.py` in the script's folder
- Can have supporting files (modules, configs, data)
- Can be run manually or on a cron schedule
- File location: `data/scripts/{scope}/{account-id}/{script-id}/script.py`
- Execution: spawned as subprocess with injected config

### Supporting Tools (NEW in latest iteration)

**Tools** (`script_type = "tool"`)
- Always global scope (shared by all accounts/scripts)
- Main file: `{python_name}.py` (e.g., `http_utils.py`)
- Importable as: `import http_utils`
- Not run directly — only imported by scripts
- File location: `data/tools/{tool-id}/{python_name}.py`
- Directory is added to PYTHONPATH when any script runs

### Variables & API Keys

- **Config Variables**: key/value pairs, optionally secret
- **API Keys**: write-only, encrypted, never revealed after creation
- **Scope**: global (all scripts) or account (scripts in that account only)
- **Injection**: merged into config dict at run time via `get_config()`

### InfoTables

- Named data tables scripts read/write
- Schema-less rows (columns defined by first insert)
- Scope: global or account
- Access: `get_table(table_id)` → insert/update/delete/get_rows()

### Cron Jobs (Updated with name + description)

- Schedule a script to run automatically
- Expression: 5-field cron format
- **NEW**: optional `name` and `description` fields (for UX)
- Managed via APScheduler (stores schedule in DB + scheduler state)
- Only one run per script at a time (enforced)

### Executions

- Record of one script run
- Status lifecycle: `queued` → `running` → `success`/`failed`/`timeout`/`interrupted`
- Logs: stdout/stderr/API calls (captured in real-time)
- Version snapshot: preserved on script.py save

---

## Database & Models

### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `scripts` | Script metadata | id, scope, account_id, name, file_path, **script_type** (new), enabled, timeout_seconds |
| `script_versions` | Version history of script.py | script_id, version_number, code, label, created_at |
| `script_permissions` | Table access per script | script_id, can_read_tables, can_write_tables, can_create_tables |
| `cron_jobs` | Scheduled triggers | script_id, cron_expression, **name** (new), **description** (new), enabled, next_run, last_run |
| `executions` | Run records | script_id, status, started_at, finished_at, return_code |
| `execution_logs` | Stdout/stderr/API logs | execution_id, stream, content, timestamp |
| `variables` | Secrets + config | scope, account_id, name, value_encrypted, is_secret, variable_type |
| `info_tables` | Data table metadata | scope, account_id, name, schema_json |
| `info_table_rows` | Rows in tables | table_id, row_data_json, created_at, updated_at |
| `accounts` | Multi-tenancy | id, name |
| `notifications` | Alerts (system health, etc) | level, category, message, dismissed_at |
| `system_metrics` | CPU/memory/disk samples | metric_name, value, recorded_at |

### Relationships

```
Account
  ├─ Scripts (1:N, cascade delete)
  ├─ Variables (1:N)
  └─ InfoTables (1:N)

Script
  ├─ ScriptPermission (1:1)
  ├─ CronJobs (1:N, cascade)
  ├─ Executions (1:N, cascade)
  └─ ScriptVersions (1:N, cascade)

Execution
  └─ ExecutionLogs (1:N, cascade)

InfoTable
  └─ InfoTableRows (1:N, cascade)
```

---

## Backend API

### Authentication
Currently **none** (development). Future: OAuth/JWT via `security.py`.

### Key Endpoints

**Scripts**
- `GET /scripts` — list scripts (filter: `account_id`, `script_type`)
- `POST /scripts` — create script (auto-scaffolds file on disk)
- `GET /scripts/{id}` — fetch one
- `PATCH /scripts/{id}` — update metadata
- `DELETE /scripts/{id}` — remove (cascades: versions, executions, cron jobs, permissions)
- `GET /scripts/{id}/content` — read main file (`script.py` for scripts, `{python_name}.py` for tools)
- `PUT /scripts/{id}/content` — save + auto-version
- `GET /scripts/{id}/files` — list all files in script directory
- `GET /scripts/{id}/files/{path}` — read a specific file
- `PUT /scripts/{id}/files/{path}` — write a file
- `POST /scripts/{id}/files` — create new file in script directory
- `DELETE /scripts/{id}/files/{path}` — remove file (not the main file)
- `POST /scripts/{id}/upload` — binary-safe multipart file upload

**Cron Jobs**
- `GET /cron-jobs` — list (filter: `script_id`)
- `POST /cron-jobs` — create (with `name`, `description`)
- `PATCH /cron-jobs/{id}` — update expression, enabled, name, description
- `DELETE /cron-jobs/{id}` — remove
- `POST /cron-jobs/{id}/pause` — disable
- `POST /cron-jobs/{id}/resume` — enable

**Executions**
- `GET /executions` — list (filter: `script_id`, `limit`, `status`)
- `POST /executions` — trigger run (checks single-instance constraint)
- `POST /executions/{id}/cancel` — terminate + mark interrupted
- `GET /executions/{id}/logs` — stream logs

**Internal** (called by `conduit-helper` from running scripts)
- `POST /internal/log-api-call` — log outbound HTTP call (requires `X-Execution-ID` header)

### Error Handling

- `404` — resource not found
- `400` — validation or path-traversal error
- `422` — invalid cron expression or schema validation error
- Error responses include a `detail` string

---

## Frontend

### Architecture

- **State**: React Query for API caching + Tanstack React Query
- **UI**: Tailwind CSS, custom components
- **Editor**: Monaco Editor (loaded via `onMount` callback, imperative `setValue()` for file switching)
- **Context**: AccountContext for global account filter

### Key Pages

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/` | Metrics, health status |
| Scripts | `/scripts` | List, create, run, enable/disable |
| Script Detail | `/scripts/{id}` | Editor, file browser, version history |
| **Tools** (NEW) | `/tools` | List, create, enable/disable tools |
| **Tool Detail** (NEW) | `/tools/{id}` | Same editor as Script Detail (imports show in meta) |
| Cron Jobs | `/cron-jobs` | List, create, pause/resume schedules |
| Executions | `/executions` | Run history, logs, filtering |
| Variables | `/variables` | Create secrets + config, reveal/rotate |
| Tables | `/tables` | List, create tables |
| Table Detail | `/tables/{id}` | View/edit rows inline |
| Docs | `/docs` | In-app reference (queries, dev fixtures, etc.) |

### Editor (`ScriptDetail.jsx`) — Key Implementation Details

1. **Main file name is dynamic** (`mainFileName` state):
   - Scripts: `script.py`
   - Tools: `{python_name}.py`
   - Set once script loads via: `setMainFileName(script.file_path.split('/').pop())`

2. **File loading**:
   - Main file: uses `/content` endpoint (versioned)
   - Other files: uses `/files/{path}` endpoint (no version history)
   - Check: `if (path === mainFileName)` to decide endpoint

3. **Dirty state**: `dirtyFiles` Set tracks unsaved files per path

4. **File cache**: `fileCache` ref stores content across file switches

5. **Save dispatch**:
   ```js
   if (path === mainFileName)
     saveMainMutation()  // /content endpoint
   else
     saveFileMutation()  // /files endpoint
   ```

6. **Drag-and-drop**: Card-level drop zone covers sidebar + editor; uses `webkitGetAsEntry()` for recursive directory upload

7. **Tools in ScriptDetail**: `isTool` flag hides Run button, execution history, and injected config panel

### API Client Pattern (`api/client.js`)

```js
const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  patch: (path, body) => request('PATCH', path, body),
  delete: (path) => request('DELETE', path),
  postForm: (path, formData) => requestForm('POST', path, formData),
}
```

Multipart uploads use `api.postForm()` (no Content-Type header — browser sets it).

---

## Scripts & Supporting Tools

### Script File Structure

```
data/scripts/global/{script-id}/
  script.py              # Entry point (always present)
  module.py              # Import as: from module import ...
  fixtures/
    data.json           # Static data file
  config_fixtures/
    config.json         # For local dev mode (CONDUIT_DEV_MODE=1)
```

### Tool File Structure

```
data/tools/{tool-id}/
  {python_name}.py      # Main importable module
  models.py             # Import as: from {python_name}.models import ...
  fixtures/             # Optional supporting data
```

### Using a Tool in a Script

```python
# Import from the tool (directory is on PYTHONPATH at run time)
from http_utils import get_client, format_response

config = get_config()
client = get_client(api_key=config["API_KEY"])
result = client.list_items()
formatted = format_response(result)
print(formatted)
```

### Runner PYTHONPATH Injection (Key Detail)

In `runner_service.py` → `_execute()`:

```python
# Get all enabled tools
tool_scripts = db.query(Script).filter(
    Script.script_type == "tool",
    Script.enabled.is_(True)
).all()

# Add each tool's directory to PYTHONPATH
tool_dirs = [str(Path(t.file_path).parent) for t in tool_scripts]
env = os.environ.copy()
if tool_dirs:
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(tool_dirs + ([existing] if existing else []))

# Pass env to subprocess
await asyncio.create_subprocess_exec(
    sys.executable,
    script.file_path,
    ...,
    env=env,
)
```

This is how `import http_utils` resolves to `data/tools/{id}/http_utils.py`.

---

## Common Workflows

### Adding a New Feature

1. **Plan**: Use EnterPlanMode to design architecture and identify files
2. **Backend**:
   - Add DB columns (models.py) + schema classes (schemas/)
   - Add API routes (api/) + business logic (services/)
3. **Frontend**:
   - Add components (pages/) or update existing ones
   - Add API client functions (api/) if needed
4. **Test**: Manual test via UI + verify DB state
5. **Document**: Update developer_documentation.md + in-app Docs

### Creating a Script

1. UI: Scripts → New Script
2. Enter name, description, scope, timeout
3. System: scaffolds `script.py` at `data/scripts/{scope}/{account-id}/{script-id}/script.py`
4. User edits code in Monaco editor
5. User adds supporting files (drag-drop or create via UI)
6. User saves (main file is versioned)

### Creating a Supporting Tool

1. UI: Tools → New Tool
2. Enter name, description
3. System: derives `python_name` (e.g., "HTTP Utils" → `http_utils`)
4. System: scaffolds main file at `data/tools/{id}/http_utils.py`
5. User edits code and adds supporting files
6. User saves (main file is versioned)
7. Any script can now `import http_utils`

### Scheduling a Script

1. UI: Cron Jobs → Schedule Script
2. Select script, cron expression (or use builder)
3. **NEW**: Optionally add name (e.g., "Morning Sync") and description
4. System: APScheduler registers job, next_run is computed
5. On each trigger: runner spawns subprocess, injects config, captures logs

### Running a Script Manually

1. UI: Scripts list or Script Detail
2. Click "Run Now"
3. System: checks single-instance constraint (rejects if already running/queued)
4. Runner queues execution (respects max_concurrent_scripts limit)
5. Subprocess spawns with PYTHONPATH including all enabled tools
6. Logs stream in real-time to Execution log panel

---

## Important Implementation Details

### Single-Instance Enforcement

Before each run, the runner checks:

```python
existing = db.query(Execution).filter(
    Execution.script_id == script_id,
    Execution.status.in_([ExecutionStatus.RUNNING, ExecutionStatus.QUEUED])
).first()
if existing:
    raise ScriptAlreadyRunningError(...)
```

This prevents concurrent runs of the same script (file locking, API call duplication, race conditions).

### Config Injection

Before spawning a subprocess:

```python
config_path = create_config(execution_id, script, db)
# Writes temp file: data/tmp/run_{execution_id}.json
# Contains: merged Variables (global + account) as dict

proc = await create_subprocess_exec(
    ...,
    f"--conduit-config={config_path}",
    f"--conduit-execution-id={execution_id}",
    ...
)
# Script reads via: conduit.get_config()
```

File is deleted after run (or on server shutdown).

### Execution Status Lifecycle

```
queued (waiting for concurrency slot)
  ↓
running (subprocess active)
  ↓
success (exit code 0) ✓
failed (exit code != 0) ✗
timeout (exceeded timeout_seconds) ⏱
interrupted (server shutdown or user cancel) 🛑
```

### Version History

Every save of the main file (script.py or tool's main file) creates a version:

```python
ScriptVersion(
    script_id=script_id,
    version_number=next_number,
    code=content,
    label=optional_user_label,  # e.g., "Stable release"
    created_at=now(),
)
```

Revert loads old code and saves as new version (preserves audit trail).

### Encryption

Secrets (`Variable.value_encrypted`) use Fernet (symmetric, key in `.secret_key` file):

```python
from cryptography.fernet import Fernet

f = Fernet(key)
encrypted = f.encrypt(secret_bytes)
decrypted = f.decrypt(encrypted_bytes)
```

Key is generated once on first startup (must be backed up).

### Execution Log Streams

Three log streams per execution:

- **stdout** (LogStream.STDOUT): script print() output
- **stderr** (LogStream.STDERR): errors, tracebacks, warnings
- **api** (LogStream.API): outbound HTTP calls logged via `log_api_call()`

Each log line has a timestamp (when written, not when read).

---

## Database & Models

### Adding a New Column

1. Add the column to the SQLAlchemy model (models.py)
2. Run SQLite `ALTER TABLE` manually (SQLAlchemy's `create_all` doesn't modify existing tables)
3. Set a sensible default in migrations or via app logic

Example:
```python
# models.py
class CronJob(Base):
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

Then:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/conduit.db')
conn.execute('ALTER TABLE cron_jobs ADD COLUMN name VARCHAR(255)')
conn.commit()
"
```

### Querying with Filters

Common patterns in the backend:

```python
# Single row
script = db.query(Script).filter_by(id=script_id).first()

# Multiple rows with filter
scripts = db.query(Script).filter(
    Script.account_id == account_id,
    Script.script_type == "script"
).all()

# Ordering
scripts = db.query(Script).order_by(Script.name).all()

# Count
count = db.query(Execution).filter_by(script_id=script_id).count()
```

---

## Debugging

### Backend Logs

Check stdout during `uvicorn` startup:

```
INFO:     app: Logging configured — level=INFO
INFO:     app.main: Conduit platform starting up...
INFO:     app.db.session: Database initialized — 15 tables ready...
```

During execution, logs appear in runner logs:

```
INFO: Started execution {execution_id} (script={script_id}, pid=12345)
...
INFO: Execution {execution_id} finished — status=success return_code=0
```

### Frontend Errors

Check browser console (F12) for API errors and React warnings.

API errors usually include a `detail` string from the backend.

### Database Inspection

Quick SQLite inspection:

```bash
sqlite3 data/conduit.db

# Common queries
SELECT id, name, script_type FROM scripts;
SELECT id, cron_expression, name, enabled FROM cron_jobs;
SELECT id, status, started_at FROM executions ORDER BY started_at DESC LIMIT 5;
SELECT content FROM execution_logs WHERE execution_id = '...' LIMIT 10;
```

---

## Testing

Currently minimal. Future:

- **Backend**: pytest for API endpoints, services
- **Frontend**: Vitest for components, API mocks
- **E2E**: Playwright for user workflows

For now, manual testing via UI is primary method.

---

## Deployment (Future)

Placeholders:

- **Secrets**: `.secret_key` must be backed up and rotated
- **Database**: SQLite suitable for single-instance; migrate to PostgreSQL for HA
- **Migrations**: Current `create_all` won't work with migrations; add Alembic for prod
- **Logging**: Ship logs to external service (Datadog, LogRocket, etc.)
- **Monitoring**: Instrument runner, scheduler, API with observability

---

## When You Make Changes

**Update this file when you:**

- Add a new database model or column
- Add a new API endpoint
- Change execution behavior
- Add/change a frontend page
- Introduce a new service or major component
- Change how scripts or tools are stored/executed

**Example**: Adding a new field to CronJob:

1. Update `backend/app/db/models.py` (add column)
2. Update `backend/app/schemas/cron_jobs.py` (add field to request/response)
3. Update `backend/app/api/cron_jobs.py` (handle field in create/update)
4. Update `frontend/src/pages/CronJobs.jsx` (show field in UI)
5. **Update this file**: add the field to the [Core Tables](#core-tables) section

---

**Last updated**: 2026-05-10  
**Maintained by**: Conduit development team
