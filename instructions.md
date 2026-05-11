# Conduit - Architecture & Build Instructions

## Iteration: 1 (Initial Architecture & Build)
**Date:** 2026-05-07 → 2026-05-10
**Status:** Iteration 1 complete. Backend foundation built, tested end-to-end, and production-ready.

---

## 1. Project Overview

Conduit is a multi-tenant Python automation platform. It runs custom Python scripts on schedules or on demand. Scripts are organized at the Global or Account level. The platform handles scheduling, execution tracking, variable management, and structured data tables. Scripts focus only on their business logic.

**Core principle:** The platform handles infrastructure. Scripts handle work.

---

## 2. Build Philosophy (Read Before Every Iteration)

These rules apply to every file, every iteration, no exceptions.

1. **Clean, human-readable code over clever code.** Optimize for the next person reading it.
2. **Split by function.** No god-files. Each module has one clear responsibility.
3. **Never assume. Ask.** If a requirement is unclear, ask before building.
4. **Push back on bad decisions.** If a request conflicts with sound design, raise it before implementing.
5. **Best practices always.** Security, error handling, type hints, docstrings, tests where they matter.
6. **Design for expansion.** Every module should be replaceable without rewriting the app.
7. **Take the time to do it right.** Quality over speed.
8. **Update this file after every iteration.** New decisions, new patterns, new gotchas all go here.

---

## 3. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI | Async-native, auto OpenAPI docs, pairs well with React |
| Frontend | React + Vite | Fast dev loop, Monaco editor support, modern |
| Database | SQLite | Simple to start, file-based, sufficient for single-VPS scale |
| Scheduler | APScheduler | In-process, persistent jobstore via SQLite, no extra infra |
| Code Editor (UI) | Monaco | VS Code's editor, best-in-class syntax/intellisense |
| Process Mgmt | Python `asyncio.subprocess` | Track subprocess lifecycle natively |
| System Metrics | `psutil` | Cross-platform standard for system monitoring |
| Encryption | `cryptography` (Fernet) | Standard symmetric encryption library |
| Helper Package | `conduit-helper` (local pip pkg) | Installable for local dev parity |
| Frontend Table | TanStack Table + react-virtual | Virtual scrolling for thousands of rows |
| Cron Parsing | `croniter` + `cron-descriptor` | Validation + human-readable previews |

---

## 4. Repository Structure (Monorepo)

```
conduit/
├── backend/                 # FastAPI app
│   ├── app/
│   │   ├── api/             # Route handlers (one file per resource)
│   │   ├── core/            # Config, security, encryption, settings
│   │   ├── db/              # SQLAlchemy models, session, migrations
│   │   ├── services/        # Business logic (script runner, scheduler, etc.)
│   │   ├── schemas/         # Pydantic request/response models
│   │   └── main.py          # App entrypoint
│   ├── tests/
│   └── requirements.txt
├── frontend/                # React + Vite app
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Route-level pages
│   │   ├── hooks/           # Custom React hooks
│   │   ├── api/             # API client (one file per resource)
│   │   ├── context/         # React context (account selector, theme, etc.)
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── helper/                  # conduit-helper pip package
│   ├── conduit/
│   │   ├── __init__.py
│   │   ├── config.py        # get_config()
│   │   ├── tables.py        # get_table(), write helpers
│   │   ├── logging.py       # API call logging utility
│   │   ├── client.py        # HTTP client for platform API (dev mode)
│   │   └── fixtures.py      # Local fixture loader
│   ├── cli.py               # conduit CLI (export-fixtures, etc.)
│   ├── setup.py
│   └── README.md
├── installers/
│   ├── install.py           # Cross-platform Python installer
│   ├── install.ps1          # Windows PowerShell
│   ├── install.sh           # Mac/Linux Bash
│   └── install_helper.py    # Standalone helper installer for dev
├── examples/                # Working sample scripts
│   ├── 01_hello_world/
│   ├── 02_using_config/
│   ├── 03_reading_tables/
│   ├── 04_writing_tables/
│   └── 05_api_logging/
├── docs/                    # Markdown documentation
│   ├── platform/            # Admin/setup docs
│   ├── scripts/             # Script author guide
│   └── architecture/        # Internal architecture docs
├── data/                    # Runtime data (gitignored)
│   ├── conduit.db
│   ├── scripts/
│   │   ├── global/
│   │   └── accounts/{account_id}/
│   ├── logs/
│   └── .secret_key          # Encryption key (chmod 600)
├── instructions.md          # THIS FILE
└── README.md
```

---

## 5. Data Model (High Level)

### Tables (DB)

- `accounts` — id, name, created_at
- `scripts` — id, scope (global/account), account_id (nullable), name, file_path, description, enabled, created_at, updated_at
- `script_permissions` — script_id, can_read_tables, can_write_tables, can_create_tables
- `cron_jobs` — id, script_id, cron_expression, enabled, last_run, next_run
- `executions` — id, script_id, started_at, finished_at, return_code, status (running/success/failed/timeout)
- `execution_logs` — execution_id, stream (stdout/stderr/api), content, timestamp
- `variables` — id, scope (global/account), account_id (nullable), name, value_encrypted, is_secret, created_at
- `info_tables` — id, scope (global/account), account_id (nullable), name, schema_json, created_at
- `info_table_rows` — id, table_id, row_data_json, created_at, updated_at
- `notifications` — id, level (info/warn/critical), category, message, metadata_json, created_at, dismissed_at (nullable)
- `system_metrics` — id, metric_name, value, recorded_at (rolling, retained 30 days)
- `users` — id, username, password_hash, role, enabled (TABLE EXISTS, UNUSED until login feature)
- `sessions` — id, user_id, token, expires_at (TABLE EXISTS, UNUSED until login)

**Note:** `users` and `sessions` tables exist from day one but are unused. This avoids painful migrations later.

### Filesystem

- Scripts live at `data/scripts/global/{script_id}/script.py` or `data/scripts/accounts/{account_id}/{script_id}/script.py`
- Each script directory may contain a `requirements.txt` (future iteration: per-script venv support)
- DB stores the canonical path; sync check on startup logs warnings if files missing

---

## 6. Module Responsibilities

### Backend Services (each is one module, swappable)

- **`scheduler_service`** — Wraps APScheduler. Public interface: `add_job`, `remove_job`, `pause_job`, `list_jobs`. Underlying engine swappable to Celery later without touching callers.
- **`runner_service`** — Spawns subprocesses, tracks PID, enforces concurrency limit, manages execution lifecycle. Writes to `executions` and `execution_logs`.
- **`config_injector_service`** — Builds the encrypted temp config file for a script run, sets file permissions, cleans up post-run.
- **`encryption_service`** — Reads `.secret_key`, encrypts/decrypts values via Fernet. All variable read/write goes through this.
- **`tables_service`** — CRUD for info tables and rows. Enforces script permissions when accessed via API.
- **`metrics_service`** — Collects system metrics on a schedule (every 30s), writes to `system_metrics`, evaluates thresholds, generates notifications.
- **`notifications_service`** — Creates, lists, and dismisses notifications. Notifications never auto-resolve.

### Frontend Pages

- **Dashboard** — System health, recent executions, active jobs
- **Scripts** — List, create, edit (Monaco), run, view history
- **Cron Jobs** — Visual builder + raw expression input with preview
- **Variables** — Manage global and account variables (secrets masked)
- **Tables** — Spreadsheet-style editor, virtual scrolling
- **Notifications** — Full notification history
- **Settings** — Concurrency limit, monitoring thresholds, account management
- **Docs** — In-app documentation page

---

## 7. Script Execution Flow

1. Trigger fires (cron or manual run)
2. `runner_service` checks concurrency limit
   - If at limit, queue the job
   - If under limit, proceed
3. `config_injector_service` decrypts variables for the script's scope, writes JSON to `data/tmp/run_{execution_id}.json` with `chmod 600`
4. Subprocess spawned: `python {script_path} --conduit-config={tmp_path} --conduit-execution-id={id}`
5. stdout/stderr streamed and persisted to `execution_logs`
6. Script uses `conduit-helper` to log API calls back to platform via local HTTP endpoint
7. On exit (success, failure, timeout):
   - Return code captured
   - Temp config file securely deleted
   - Execution row updated
   - Slot released, next queued job pulled
8. History retained forever

---

## 8. Helper Package (`conduit-helper`)

### Public API
```python
from conduit import get_config, get_table, log_api_call

config = get_config()           # dict-like, includes secrets, never logged
api_key = config.get("API_KEY")

customers = get_table("customer_list")  # iterable of rows
for row in customers:
    log_api_call(
        method="GET",
        url=f"https://api.example.com/{row['id']}",
        status_code=200,
        duration_ms=145,
    )
```

### Two Modes

**Production mode (running inside Conduit):**
- Reads config from CLI arg path
- Reads execution ID from CLI arg
- Writes logs via local HTTP API to platform

**Dev mode (local development):**
- Activated by `CONDUIT_DEV_MODE=1` env var
- Reads config from `./conduit_fixtures/config.json`
- Reads tables from `./conduit_fixtures/{table_name}.json`
- Logs print to stdout instead of API call

### Fixture Export CLI
```bash
conduit export-fixtures --account-id <id> --output ./conduit_fixtures
conduit export-fixtures --table customer_list
```

---

## 9. Security Practices (Non-Negotiable)

- Encryption key stored at `data/.secret_key`, generated on first install, file mode `600`, owner-only
- All secrets encrypted at rest via Fernet (AES-128 + HMAC)
- Secrets never written to logs (helper enforces this; platform redacts known-secret variable names)
- Temp config files use `chmod 600` and are deleted post-execution (also on crash via cleanup hook)
- No secrets in CLI args or env vars (avoids `ps aux` exposure)
- SQL via parameterized queries (SQLAlchemy ORM enforces this)
- Input validation via Pydantic schemas
- Future login feature: bcrypt password hashing, session tokens with expiry, CSRF protection
- Frontend XSS protection: React escaping by default; Monaco content treated as code, not HTML

---

## 10. Server Health Monitoring

**Metrics collected every 30 seconds:**
- CPU usage %
- Memory usage %
- Disk space % (data directory)
- Active script count vs concurrency limit
- Script queue depth
- Failed script rate (rolling 1 hour)

**Thresholds (configurable per metric):**
- Warn: 75% (default)
- Critical: 90% (default)

**Notifications:**
- Generated on threshold cross
- Bell badge in top bar with unread count
- Persistent (no auto-resolve)
- Manual dismissal only
- Global scope only

---

## 11. Concurrency

- Default max concurrent scripts: **10** (configurable via Settings page)
- Overflow goes to in-memory queue (FIFO)
- Queue depth exposed as a metric and visible in dashboard
- On app shutdown: running scripts marked as `interrupted`, queue persisted to DB, restored on startup

---

## 12. Authentication (Architected, Not Built)

- `users` and `sessions` tables exist
- `core/security.py` module placeholder created with TODO
- All API routes designed to accept an optional `current_user` dependency that returns `None` today
- When login is enabled, the dependency becomes mandatory
- Login is **global only** (admin manages all accounts)

---

## 13. Open Questions / Future Iterations

These are intentionally deferred. Do not build until prompted.

- Container-based script isolation (Docker)
- Multi-instance horizontal scaling (would require Celery + Redis)
- Login implementation
- Per-script Python virtual environments
- Webhook triggers (in addition to cron)
- Script versioning / git integration
- Audit log for all admin actions
- Backup/restore tooling

---

## 14. Iteration Workflow

After every build iteration:

1. Update this file with what was built
2. Note any new patterns established
3. Note any gotchas discovered
4. Update Open Questions section
5. Tag the iteration with date and a one-line summary

---

## 15. Iteration Log

| # | Date | Summary |
|---|------|---------|
| 1 | 2026-05-07 | Initial architecture defined. No code written. |
| 2 | 2026-05-10 | Full backend built and smoke-tested end-to-end. All 10 build steps + smoke test complete. Implementation ready for Iteration 2 (frontend + UI enhancements). |
| 3 | 2026-05-10 | Security hardening: CORS fix, rate limiting, request size limits, ScriptDetail black-page bug fixed. Auth, encryption key backup, and audit logging implemented (all 10/10 tests pass). |

---

## 16. Iteration 2 — What Was Built

**Backend (all complete, smoke-tested):**
- All 13 DB models with indexes on hot query columns
- 9 API route files under `/api/v1/`
- Full lifespan: logging → DB init → encryption → sync check → restore_state → scheduler → metrics
- `conduit-helper` pip package: `get_config`, `get_table`, `log_api_call`
- 5 working example scripts with `conduit_fixtures/`

**Patterns established:**
- `str | None` syntax invalid in FastAPI route signatures on Python 3.9 — always use `Optional[str]` from typing
- `list[X]` and `dict[str, X]` ARE valid in Python 3.9 body annotations (PEP 585) — only `X | Y` union fails
- `from __future__ import annotations` does NOT help FastAPI parameter resolution — fix the annotation itself
- SQLite + APScheduler deadlock: always `db.commit()` before calling `scheduler_service.add_job()` — SQLite allows only one writer; an open flush transaction blocks the jobstore write
- SQLAlchemy UUID PK gotcha: call `db.flush()` before using a new object's ID as a FK; `db.commit()` also works but flushes implicitly
- `EncryptionService` self-initializes at import time — no separate `init()` call needed
- `VariableResponse` uses `model_validator(mode="before")` to decrypt ORM objects transparently — routes return raw ORM objects; schema handles the transform

**Smoke test patterns (Iteration 1, 2026-05-10):**
- APScheduler triggers cron jobs within 1-5 seconds of the minute boundary — extremely responsive, not tied to manual polling
- Execution logs stream correctly to all three channels: stdout, stderr, api (each with timestamp and execution_id FK)
- Internal API endpoint (`/internal/log-api-call`) requires active execution — returns 401 if execution is finished; this is correct defensive behavior
- Config injection via temp file with execution ID naming (`run_{execution_id}.json`) prevents collisions and cleanup is reliable
- Server shutdown/restart cycle preserves all execution state in DB — no manual recovery needed
- Script execution triggers create automatic `ScriptVersion` rows (immutable snapshots) — backwards compat for reruns on prior code

**Gotchas:**
- pip 21.x does not support `setuptools.backends.legacy:build` — use `setuptools.build_meta` + `setup.cfg`
- Python 3.9 system pip (21.2.4) does not support editable installs from pyproject.toml — add `setup.py` + `setup.cfg`
- `notifications_service.create_notification` signature: `db` must be a required positional param, not `db=None` default — callers always have a session
- `metrics_service.evaluate_thresholds` secondary sort: always include `.order_by(..., SystemMetric.id.desc())` to get deterministic "previous reading" under high write volume
- Internal API logging endpoint only works with active executions — finish = 401 response. Use explicit execution_id guards in scripts that call `conduit.log_api_call()`

---

## 17. Iteration 3 — What Was Built

**Security hardening (all complete, smoke-tested):**

### CORS Fix
- `cors_allowed_origins` default changed from `["*"]` to `["http://localhost:5173", "http://localhost:3000"]`
- Added `@model_validator` in `config.py` that raises `ValueError` if `["*"]` is used (prevents the dangerous wildcard + credentials combination)
- CORSMiddleware restricted to explicit HTTP method and header whitelists

### Rate Limiting
- `slowapi` integrated — 60 requests/minute per IP, in-memory storage
- Returns HTTP 429 with descriptive message on violation

### Request Size Limits
- New middleware `app/middleware/size_limits.py`
- File uploads: 100 MB max → HTTP 413
- JSON payloads: 10 MB max → HTTP 413

### Authentication
- `core/security.py` fully implemented — replaced stub with real JWT + bcrypt auth
- `hash_password()` / `verify_password()` — bcrypt, 12 rounds
- `create_token()` — issues HS256 JWT, writes to `sessions` table for revocation support
- `get_current_user()` — FastAPI dependency; validates Bearer JWT, checks session table, returns User or None
- `require_user()` — raises HTTP 401 when `auth_enabled=True` and no valid token
- `auth_enabled` config flag (default `False`) — platform stays open for local dev; flip to `True` for production
- New endpoints under `/api/v1/auth/`:
  - `POST /auth/setup` — create first admin (one-time, 409 if any user exists)
  - `POST /auth/login` — returns JWT
  - `POST /auth/logout` — revokes session token
  - `GET /auth/me` — current user profile (always needs token)
  - `POST /auth/change-password` — updates hash, revokes all sessions
  - `GET /auth/status` — returns `auth_enabled`, `setup_complete`, `user_count`
- All protected routes accept `Depends(require_user)` at router-mount level — zero per-route changes needed

### Encryption Key Backup
- `config.py`: new `encryption_key: str = ""` field — maps to `ENCRYPTION_KEY` env var
- `encryption.py` priority: env var → key file → generate new key
- Allows injection from AWS Secrets Manager, Vault, or any secrets manager
- Key format: base64url-encoded Fernet key string

### Audit Logging
- New `AuditLog` DB model — append-only, never updated or deleted
- Fields: `user_id`, `username` (denormalised), `action`, `resource_type`, `resource_id`, `resource_name`, `ip_address`, `metadata_json`, `created_at`
- New `services/audit_service.py` — `audit()` function: fire-and-forget, errors never break callers
- New `api/audit.py` — `GET /api/v1/audit-logs` with filters: `action`, `resource_type`, `resource_id`, `user_id`, `limit`, `offset`
- Already wired into: `auth.setup`, `auth.login`, `auth.login_failed`, `auth.logout`, `auth.password_change`

**Patterns established:**
- `get_current_user` short-circuits (returns None) only when auth is OFF and no token is present; if a token exists it is always validated — this lets `/auth/me` work regardless of `auth_enabled`
- Audit errors must never propagate — wrap all `audit()` calls are already inside try/except in the service
- JWT secret auto-generated per process when not set via env var — set `JWT_SECRET` in `.env` for session persistence across restarts
- `require_user` at router-mount level (`dependencies=[Depends(require_user)]`) is cleaner than per-route — all new routers added to `protected` dict in `_register_routers`

**Gotchas:**
- `get_current_user` must always try to validate a token if one is present, even when `auth_enabled=False` — otherwise `/auth/me` returns 500 when user is None
- `change-password` and `/auth/me` use `get_current_user` (not `require_user`) so they always require a token, even with auth disabled
- SQLite `sessions` table token column is 1024 chars — JWT tokens fit comfortably
