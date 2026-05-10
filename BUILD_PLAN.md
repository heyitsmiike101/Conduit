# Conduit — Iteration 1 Build Plan
**Date:** 2026-05-07
**Status:** Ready to execute. No code written yet.

---

## How to Use This File

Run each step in order. Do not move to the next step until all success metrics for the current step are met. Update the `[ ]` checkboxes as you go. After all steps complete, update `instructions.md` §15 Iteration Log.

---

## Step 1 — Repo Skeleton

Create the full directory and file structure for the monorepo. No logic yet — just the folders and empty `__init__.py` files where Python packages need them.

### Directories to create
```
conduit/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── services/
│   │   └── schemas/
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       ├── api/
│       └── context/
├── helper/
│   └── conduit/
├── installers/
├── examples/
│   ├── 01_hello_world/
│   ├── 02_using_config/
│   ├── 03_reading_tables/
│   ├── 04_writing_tables/
│   └── 05_api_logging/
├── docs/
│   ├── platform/
│   ├── scripts/
│   └── architecture/
└── data/
    ├── scripts/
    │   ├── global/
    │   └── accounts/
    ├── logs/
    └── tmp/
```

### `__init__.py` files needed
- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/core/__init__.py`
- `backend/app/db/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/tests/__init__.py`
- `helper/conduit/__init__.py` *(placeholder — real content in Step 7)*

### Success Metrics
- [ ] `find conduit/ -type d | wc -l` returns ≥ 25 directories
- [ ] All `__init__.py` files exist (no import errors from empty packages)
- [ ] `backend/tests/` exists and is importable (`python -c "import tests"` from `backend/`)
- [ ] `data/` directory exists at repo root with `scripts/global/`, `scripts/accounts/`, `logs/`, `tmp/`
- [ ] `.gitignore` exists and excludes: `data/`, `*.db`, `.secret_key`, `.env`, `__pycache__/`, `node_modules/`, `dist/`

---

## Step 2 — Backend: Core Config & Encryption

Build the foundational config and encryption layer. Everything else depends on this.

### Files to create
- `backend/app/core/config.py`
- `backend/app/core/encryption.py`
- `backend/app/core/security.py`
- `backend/app/core/logging.py`
- `backend/.env.example`
- `backend/requirements.txt`

### `config.py` spec
- Pydantic `BaseSettings` class called `Settings`
- Fields: `data_dir: Path`, `secret_key_path: Path`, `max_concurrent_scripts: int = 10`, `metrics_interval_seconds: int = 30`, `warn_threshold: float = 0.75`, `critical_threshold: float = 0.90`, `database_url: str` (defaults to `sqlite:///./data/conduit.db`), `cors_allowed_origins: list[str] = ["*"]` (env: comma-separated string), `log_level: str = "INFO"`
- Exported singleton: `settings = Settings()`
- All paths resolve relative to repo root

### `logging.py` spec
- `configure_logging()` — sets root logger format to `%(asctime)s %(levelname)s %(name)s: %(message)s`, level from `settings.log_level`
- Called once at app startup from `main.py` lifespan
- Suppresses noisy loggers (`apscheduler`, `sqlalchemy.engine`) to `WARNING`

### `encryption.py` spec
- Class `EncryptionService`
- `__init__`: loads key from `settings.secret_key_path`; if file missing, generates new Fernet key, writes it, sets `chmod 600`
- `encrypt(value: str) -> str` — returns URL-safe base64 token
- `decrypt(token: str) -> str` — returns original string
- Raises `EncryptionError` (custom exception) if key missing or token invalid
- Exported singleton: `encryption_service = EncryptionService()`

### `security.py` spec
- Single function: `get_current_user() -> None`
- Docstring: `# TODO: Implement login. Returns None until auth is enabled.`
- Returns `None` always

### `requirements.txt` — pinned versions
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
apscheduler>=3.10.0
cryptography>=42.0.0
psutil>=5.9.0
httpx>=0.27.0
croniter>=2.0.0
cron-descriptor>=1.4.0
python-multipart>=0.0.9
```

### Success Metrics
- [ ] `from app.core.config import settings` — imports without error
- [ ] `settings.max_concurrent_scripts == 10`
- [ ] `from app.core.encryption import encryption_service` — imports without error
- [ ] `encryption_service.decrypt(encryption_service.encrypt("hello")) == "hello"`
- [ ] Running encrypt twice on the same string produces different tokens (Fernet is non-deterministic)
- [ ] `data/.secret_key` is created with mode `600` on first run
- [ ] Running again reuses the existing key (decrypt still works across instances)
- [ ] `from app.core.security import get_current_user; get_current_user() is None`
- [ ] `from app.core.logging import configure_logging` imports without error
- [ ] After `configure_logging()`, `logging.getLogger("app").info("test")` produces formatted output

---

## Step 3 — Database Models & Session

Define all SQLAlchemy models and the session/init utilities.

### Files to create
- `backend/app/db/models.py`
- `backend/app/db/session.py`

### `models.py` — all tables

| Model | Key Fields |
|---|---|
| `Account` | `id` (UUID pk), `name` (str, unique), `created_at` |
| `Script` | `id` (UUID pk), `scope` (enum: global/account), `account_id` (FK nullable), `name`, `file_path`, `description`, `enabled` (bool, default True), `timeout_seconds` (int nullable, default `None`), `created_at`, `updated_at` |
| `ScriptPermission` | `script_id` (FK, pk), `can_read_tables` (bool), `can_write_tables` (bool), `can_create_tables` (bool) |
| `CronJob` | `id` (UUID pk), `script_id` (FK), `cron_expression` (str), `enabled` (bool), `last_run` (datetime nullable), `next_run` (datetime nullable) |
| `Execution` | `id` (UUID pk), `script_id` (FK), `started_at`, `finished_at` (nullable), `return_code` (int nullable), `status` (enum: queued/running/success/failed/timeout/interrupted) |
| `ExecutionLog` | `id` (int pk autoincrement), `execution_id` (FK), `stream` (enum: stdout/stderr/api), `content` (text), `timestamp` |
| `Variable` | `id` (UUID pk), `scope` (enum: global/account), `account_id` (FK nullable), `name`, `value_encrypted` (text), `is_secret` (bool), `created_at` |
| `InfoTable` | `id` (UUID pk), `scope` (enum: global/account), `account_id` (FK nullable), `name`, `schema_json` (text), `created_at` |
| `InfoTableRow` | `id` (UUID pk), `table_id` (FK), `row_data_json` (text), `created_at`, `updated_at` |
| `Notification` | `id` (UUID pk), `level` (enum: info/warn/critical), `category` (str), `message` (text), `metadata_json` (text nullable), `created_at`, `dismissed_at` (datetime nullable) |
| `SystemMetric` | `id` (int pk autoincrement), `metric_name` (str), `value` (float), `recorded_at` |
| `User` | `id` (UUID pk), `username` (str, unique), `password_hash` (str), `role` (str), `enabled` (bool) |
| `Session` | `id` (UUID pk), `user_id` (FK), `token` (str, unique), `expires_at` (datetime) |

- All UUID PKs use `default=uuid.uuid4`
- All `created_at` fields use `default=datetime.utcnow`
- `updated_at` fields use `onupdate=datetime.utcnow`
- Use SQLAlchemy 2.x mapped column style (`Mapped[str]`, `mapped_column`)

### `session.py` spec
- `engine` — created from `settings.database_url`
- `SessionLocal` — `sessionmaker(bind=engine)`
- `get_db()` — FastAPI dependency, yields session, closes on exit
- `init_db()` — calls `Base.metadata.create_all(engine)`, logs table count

### `db/__init__.py` spec
- Re-exports `Base`, `SessionLocal`, `get_db`, `init_db` so callers can `from app.db import Base, get_db`

### Success Metrics
- [ ] `from app.db.models import Account, Script, Execution` — imports without error
- [ ] `from app.db.session import init_db, get_db` — imports without error
- [ ] `from app.db import Base, get_db` works (re-exports verified)
- [ ] `init_db()` creates `conduit.db` with all 13 tables
- [ ] `sqlite3 data/conduit.db ".tables"` lists: `accounts scripts script_permissions cron_jobs executions execution_logs variables info_tables info_table_rows notifications system_metrics users sessions`
- [ ] Inserting and querying an `Account` row works via `SessionLocal`
- [ ] Re-running `init_db()` does not error or drop existing data

---

## Step 4 — Pydantic Schemas

Request/response models for every resource. These are the contracts for the API.

### Files to create
- `backend/app/schemas/accounts.py`
- `backend/app/schemas/scripts.py`
- `backend/app/schemas/variables.py`
- `backend/app/schemas/executions.py`
- `backend/app/schemas/cron_jobs.py`
- `backend/app/schemas/tables.py`
- `backend/app/schemas/notifications.py`

### Pattern for each schema file
Each file contains three classes:
1. `{Resource}Create` — fields required to create
2. `{Resource}Update` — all fields optional (for PATCH)
3. `{Resource}Response` — full object returned from API (includes `id`, timestamps)

`Response` classes set `model_config = ConfigDict(from_attributes=True)` (SQLAlchemy ORM compat).

### Special schema notes
- `VariableResponse` — never includes `value_encrypted`; includes `value: str | None` that is populated after decryption (and masked as `"***"` if `is_secret=True` and caller does not have elevated access)
- `ExecutionResponse` — includes `status`, `return_code`, derived `duration_seconds: float | None`
- `CronJobCreate` — validates `cron_expression` using `croniter.is_valid()`, raises 422 if invalid
- `CronJobResponse` — includes `human_readable: str` from `cron_descriptor`
- `InfoTableCreate` — `schema_json` must be valid JSON (validated by Pydantic)
- `VariableCreate`, `ScriptCreate`, `InfoTableCreate` — Pydantic `model_validator(mode="after")` enforces: if `scope == "account"`, `account_id` must be set; if `scope == "global"`, `account_id` must be `None`. Raises 422 on mismatch.

### Success Metrics
- [ ] All 7 schema files import without error
- [ ] `CronJobCreate(cron_expression="not-a-cron")` raises `ValidationError`
- [ ] `CronJobCreate(cron_expression="0 * * * *")` passes validation
- [ ] `VariableResponse` has no field named `value_encrypted`
- [ ] All `Response` models have `model_config = ConfigDict(from_attributes=True)`
- [ ] `VariableCreate(scope="account", account_id=None, ...)` raises `ValidationError`
- [ ] `VariableCreate(scope="global", account_id="some-uuid", ...)` raises `ValidationError`

---

## Step 5 — Services

The business logic layer. Each service is one file with one responsibility.

### Files to create
- `backend/app/services/encryption_service.py`
- `backend/app/services/scheduler_service.py`
- `backend/app/services/runner_service.py`
- `backend/app/services/config_injector_service.py`
- `backend/app/services/tables_service.py`
- `backend/app/services/notifications_service.py`
- `backend/app/services/metrics_service.py`

---

### `encryption_service.py`
Thin wrapper around `core/encryption.py` for use with the `Variable` model.

- `encrypt_variable(value: str) -> str`
- `decrypt_variable(token: str) -> str`
- `get_variable_value(variable: Variable, reveal_secret: bool = False) -> str` — returns `"***"` for secrets unless `reveal_secret=True`

**Metrics:**
- [ ] `encrypt_variable` / `decrypt_variable` round-trips correctly
- [ ] Secrets return `"***"` by default from `get_variable_value`

---

### `scheduler_service.py`
Full APScheduler wrapper. Underlying engine is swappable without touching callers.

Public interface:
- `add_job(script_id: str, cron_expression: str) -> str` — returns APScheduler job ID
- `remove_job(job_id: str) -> None`
- `pause_job(job_id: str) -> None`
- `resume_job(job_id: str) -> None`
- `list_jobs() -> list[dict]` — returns `[{job_id, script_id, cron_expression, next_run, paused}]`
- `start()` / `shutdown()` — lifecycle methods

Uses `APScheduler` with `SQLAlchemyJobStore` pointed at `conduit.db`. On trigger, calls `runner_service.run_script(script_id)`.

**Metrics:**
- [ ] `scheduler_service.start()` does not error
- [ ] `add_job` returns a non-empty string ID
- [ ] `list_jobs()` returns the added job
- [ ] `remove_job` removes it from `list_jobs()`
- [ ] `pause_job` / `resume_job` toggles paused state in `list_jobs()`
- [ ] Scheduler survives app restart (persisted to SQLite)

---

### `config_injector_service.py`
Builds and cleans up the secure temp config file for each script run.

- `create_config(execution_id: str, script: Script, db: Session) -> Path`
  - Queries variables in scope (global + account if applicable)
  - Decrypts all values
  - Writes JSON to `data/tmp/run_{execution_id}.json`
  - Sets `chmod 600`
  - Returns path
- `cleanup_config(execution_id: str) -> None`
  - Deletes `data/tmp/run_{execution_id}.json`
  - Logs warning if file not found (already cleaned)

**Metrics:**
- [ ] `create_config` produces a file with mode `600`
- [ ] File contains all variables for the script's scope as a flat dict
- [ ] `cleanup_config` deletes the file
- [ ] `cleanup_config` called twice does not raise

---

### `runner_service.py`
Core of the platform. Spawns and tracks script subprocesses.

State:
- `_running: dict[str, asyncio.subprocess.Process]` — execution_id → process
- `_queue: asyncio.Queue` — pending script runs

Public interface:
- `async run_script(script_id: str, db: Session) -> str` — returns `execution_id`; queues if at concurrency limit
- `async cancel_script(execution_id: str) -> None` — sends SIGTERM, marks as interrupted
- `get_active_executions() -> list[str]` — returns list of running execution IDs
- `get_queue_depth() -> int`
- `async shutdown() -> None` — marks all `_running` executions as `interrupted`, persists pending `_queue` script_ids to `data/queue_state.json`, then awaits subprocess termination
- `async restore_state() -> None` — on startup, loads `data/queue_state.json` if present, re-queues script_ids, deletes the file

Execution lifecycle (per §7 of instructions.md):
1. Check concurrency — queue if full
2. Create `Execution` row with status `running`
3. Call `config_injector_service.create_config`
4. Spawn: `asyncio.create_subprocess_exec("python", script_path, f"--conduit-config={config_path}", f"--conduit-execution-id={execution_id}")`
5. Stream stdout → `ExecutionLog(stream="stdout")`, stderr → `ExecutionLog(stream="stderr")` — write in chunks
6. Wait for exit
7. Call `config_injector_service.cleanup_config`
8. Update `Execution` row: `status`, `return_code`, `finished_at`
9. Release slot, pull next from queue

Timeout: configurable per-script (default: none). If timeout, send SIGTERM → wait 5s → SIGKILL → mark `timeout`.

**Metrics:**
- [ ] `run_script` for a `print("hello")` script creates an `Execution` row with `status="success"`
- [ ] `ExecutionLog` rows exist with `stream="stdout"` containing `"hello"`
- [ ] `run_script` for a script that `sys.exit(1)` creates row with `status="failed"`, `return_code=1`
- [ ] Running 11 scripts when `max_concurrent_scripts=10` queues the 11th (`get_queue_depth() == 1`)
- [ ] Temp config file is deleted after run (success and failure)
- [ ] `cancel_script` on a running execution marks it `interrupted`
- [ ] Killing the server during a run leaves `Execution.status == "interrupted"` (not `running`)
- [ ] Server restart with non-empty `data/queue_state.json` restarts queued runs and deletes the file

---

### `tables_service.py`
CRUD for info tables and rows with permission enforcement.

- `create_table(name: str, scope: str, account_id: str | None, schema: dict, db: Session) -> InfoTable`
- `get_table(table_id: str, db: Session) -> InfoTable`
- `list_tables(scope: str, account_id: str | None, db: Session) -> list[InfoTable]`
- `delete_table(table_id: str, db: Session) -> None`
- `insert_row(table_id: str, row_data: dict, script_id: str | None, db: Session) -> InfoTableRow`
  - If `script_id` provided, checks `ScriptPermission.can_write_tables`; raises `PermissionError` if not allowed
- `get_rows(table_id: str, db: Session) -> list[InfoTableRow]`
- `update_row(row_id: str, row_data: dict, db: Session) -> InfoTableRow`
- `delete_row(row_id: str, db: Session) -> None`

**Note:** A script with no `ScriptPermission` row is treated as "deny all" (defensive default).

**Metrics:**
- [ ] Create table, insert 3 rows, `get_rows` returns 3
- [ ] Script without `can_write_tables` raises `PermissionError` on `insert_row`
- [ ] Script with no `ScriptPermission` row at all raises `PermissionError` on `insert_row`
- [ ] `delete_table` cascades to delete all rows

---

### `notifications_service.py`
Simple CRUD. Notifications never auto-resolve.

- `create_notification(level: str, category: str, message: str, metadata: dict | None, db: Session) -> Notification`
- `list_notifications(dismissed: bool = False, db: Session) -> list[Notification]`
- `dismiss_notification(notification_id: str, db: Session) -> Notification`
- `get_unread_count(db: Session) -> int` — count of `dismissed_at IS NULL`

**Metrics:**
- [ ] Create 3 notifications, `list_notifications(dismissed=False)` returns 3
- [ ] `dismiss_notification` sets `dismissed_at` to a non-null datetime
- [ ] `list_notifications(dismissed=False)` excludes dismissed ones
- [ ] `get_unread_count` returns correct integer

---

### `metrics_service.py`
Collects system metrics on schedule. Full implementation including threshold-crossing alert logic.

- `collect_metrics(db: Session) -> dict` — gathers CPU %, memory %, disk %, active script count, queue depth, failed rate (1h); writes `SystemMetric` rows; returns dict
- `evaluate_thresholds(metrics: dict, db: Session) -> None` — for each metric in (`cpu_percent`, `memory_percent`, `disk_percent`, `failed_rate_1h`), compares to `settings.warn_threshold` and `settings.critical_threshold`. On a fresh threshold crossing (compared to previous metric value from `SystemMetric`), creates a `Notification` via `notifications_service` (level=warn or critical, category=`"system_health"`, message includes metric name + value). Does NOT generate duplicates while value remains above threshold.
- `prune_old_metrics(db: Session) -> int` — deletes `SystemMetric` rows older than 30 days, returns count deleted
- `start_collection_loop(app)` — registers APScheduler job to call `collect_metrics` every `settings.metrics_interval_seconds`

**Metrics:**
- [ ] `collect_metrics` returns dict with keys: `cpu_percent`, `memory_percent`, `disk_percent`, `active_scripts`, `queue_depth`, `failed_rate_1h`
- [ ] `SystemMetric` rows written to DB after calling `collect_metrics`
- [ ] `prune_old_metrics` deletes rows older than 30 days without touching newer ones
- [ ] Forcing `cpu_percent=0.95` produces one critical notification, not duplicates on repeat ticks
- [ ] Dropping back below threshold then re-crossing produces a new notification

---

## Step 6 — API Routes

FastAPI route handlers for every resource. Logic lives in services — routes are thin.

### Files to create
- `backend/app/api/health.py`
- `backend/app/api/accounts.py`
- `backend/app/api/scripts.py`
- `backend/app/api/variables.py`
- `backend/app/api/executions.py`
- `backend/app/api/cron_jobs.py`
- `backend/app/api/tables.py`
- `backend/app/api/notifications.py`
- `backend/app/api/internal.py`

### Route inventory

**`health.py`**
- `GET /health` → `{"status": "ok", "version": "1.0.0", "active_scripts": int, "queue_depth": int}`

**`accounts.py`**
- `GET /accounts` → `list[AccountResponse]`
- `POST /accounts` → `AccountResponse`
- `GET /accounts/{account_id}` → `AccountResponse`
- `PATCH /accounts/{account_id}` → `AccountResponse`
- `DELETE /accounts/{account_id}` → `204`

**`scripts.py`**
- `GET /scripts` → `list[ScriptResponse]` (optional `?account_id=`, `?scope=`)
- `POST /scripts` → `ScriptResponse`
  - On create: generates `id`, computes `file_path` as `data/scripts/global/{id}/script.py` (or `data/scripts/accounts/{account_id}/{id}/script.py`), creates the directory, writes a starter `script.py` (shebang + minimal `from conduit import get_config` template), creates a default `ScriptPermission` row with all flags `False`. Returns `ScriptResponse` including `file_path`.
- `GET /scripts/{script_id}` → `ScriptResponse`
- `PATCH /scripts/{script_id}` → `ScriptResponse`
- `GET /scripts/{script_id}/content` → `{"content": str}` (reads file from disk)
- `PUT /scripts/{script_id}/content` → `{"saved": true}` (writes file to disk)
- `DELETE /scripts/{script_id}` → `204`
  - Removes the on-disk script directory (best-effort; logs warning if already gone) AND deletes the DB row. Cascades to `ScriptPermission`, `CronJob`, `Execution`, `ExecutionLog`.

**`variables.py`**
- `GET /variables` → `list[VariableResponse]` (masked secrets)
- `POST /variables` → `VariableResponse`
- `GET /variables/{variable_id}` → `VariableResponse`
- `PATCH /variables/{variable_id}` → `VariableResponse`
- `DELETE /variables/{variable_id}` → `204`
- `GET /variables/{variable_id}/reveal` → `{"value": str}` (unmasked — future: requires elevated auth)

**`executions.py`**
- `POST /scripts/{script_id}/run` → `ExecutionResponse` (triggers `runner_service.run_script`)
- `GET /executions` → `list[ExecutionResponse]` (optional `?script_id=`, `?status=`)
- `GET /executions/{execution_id}` → `ExecutionResponse`
- `GET /executions/{execution_id}/logs` → `list[ExecutionLogResponse]` (optional `?stream=stdout|stderr|api`)
- `POST /executions/{execution_id}/cancel` → `ExecutionResponse`

**`cron_jobs.py`**
- `GET /cron-jobs` → `list[CronJobResponse]`
- `POST /cron-jobs` → `CronJobResponse`
- `GET /cron-jobs/{job_id}` → `CronJobResponse`
- `PATCH /cron-jobs/{job_id}` → `CronJobResponse`
- `DELETE /cron-jobs/{job_id}` → `204`
- `POST /cron-jobs/validate` → `{"valid": bool, "human_readable": str, "next_runs": list[datetime]}`

**`tables.py`**
- `GET /tables` → `list[InfoTableResponse]`
- `POST /tables` → `InfoTableResponse`
- `GET /tables/{table_id}` → `InfoTableResponse`
- `DELETE /tables/{table_id}` → `204`
- `GET /tables/{table_id}/rows` → `list[InfoTableRowResponse]`
- `POST /tables/{table_id}/rows` → `InfoTableRowResponse`
- `PATCH /tables/{table_id}/rows/{row_id}` → `InfoTableRowResponse`
- `DELETE /tables/{table_id}/rows/{row_id}` → `204`

**`notifications.py`**
- `GET /notifications` → `list[NotificationResponse]` (optional `?dismissed=false`)
- `GET /notifications/count` → `{"unread": int}`
- `POST /notifications/{notification_id}/dismiss` → `NotificationResponse`

**`internal.py`** — internal endpoints called by `conduit-helper` from running scripts. Identifies the caller via `X-Execution-ID` header.
- `POST /internal/log-api-call` body: `{method, url, status_code, duration_ms, metadata?}` → writes `ExecutionLog(stream="api", content=json)` for the execution_id in the header. Returns `204`.
- Header missing or invalid → `401`.

### Success Metrics
- [ ] All 9 route files import without error
- [ ] `GET /api/v1/health` returns `200` with `status: "ok"`
- [ ] `POST /api/v1/accounts` with `{"name": "Test Co"}` returns `201` with an `id` field
- [ ] `GET /api/v1/accounts/{id}` returns the created account
- [ ] `POST /api/v1/cron-jobs/validate` with `{"cron_expression": "0 * * * *"}` returns `{"valid": true, "human_readable": "Every hour"...}`
- [ ] `POST /api/v1/cron-jobs/validate` with `{"cron_expression": "bad"}` returns `{"valid": false}`
- [ ] After `POST /api/v1/scripts`, the file at `Script.file_path` exists on disk
- [ ] After `POST /api/v1/scripts`, a `ScriptPermission` row exists with all flags `False`
- [ ] `POST /api/v1/internal/log-api-call` with a valid `X-Execution-ID` header writes an `ExecutionLog` row with `stream="api"`
- [ ] `POST /api/v1/internal/log-api-call` without the header returns `401`
- [ ] FastAPI auto-generated docs at `/docs` show all routes

---

## Step 7 — App Entrypoint

Wire everything together.

### File to create
- `backend/app/main.py`

### Spec
```python
app = FastAPI(title="Conduit", version="1.0.0")

# CORS — origins read from settings.cors_allowed_origins (default ["*"])
# Lifespan context manager:
#   startup:
#     1. configure_logging()
#     2. init_db()
#     3. encryption_service init (reads/creates .secret_key)
#     4. sync check — iterate Script rows; for any whose file_path is missing on
#        disk, log WARNING and create a Notification (category="missing_script_file")
#     5. runner_service.restore_state()  # re-queue any scripts persisted at last shutdown
#     6. scheduler_service.start()
#     7. metrics_service.start_collection_loop()
#   shutdown:
#     1. scheduler_service.shutdown()
#     2. runner_service.shutdown()  # marks running as interrupted, persists queue

# Include all routers with prefix /api/v1
```

### Success Metrics
- [ ] `uvicorn app.main:app --reload` starts without errors
- [ ] Startup logs show: `Database initialized`, `Scheduler started`, `Metrics collection started`
- [ ] All routes accessible under `/api/v1/`
- [ ] `/docs` renders OpenAPI UI with all endpoints grouped by tag
- [ ] Shutdown is clean (no hanging threads)
- [ ] Manually deleting a script file from disk and restarting produces a startup `WARNING` log and a notification with category `missing_script_file`
- [ ] Killing the server while a queued execution is pending, then restarting, the queued script runs after restart

---

## Step 8 — `conduit-helper` Package

The pip package scripts import to interact with the platform.

### Files to create
- `helper/conduit/__init__.py`
- `helper/conduit/config.py`
- `helper/conduit/tables.py`
- `helper/conduit/logging.py`
- `helper/conduit/client.py`
- `helper/conduit/fixtures.py`
- `helper/cli.py`
- `helper/setup.py`
- `helper/README.md`

### `__init__.py` (pinned contract)
```python
from .config import get_config
from .tables import get_table
from .logging import log_api_call

__all__ = ["get_config", "get_table", "log_api_call"]
__version__ = "0.1.0"
```

### `config.py`
- `get_config() -> dict`
- Prod mode: reads JSON from path in `--conduit-config` CLI arg
- Dev mode (`CONDUIT_DEV_MODE=1`): reads `./conduit_fixtures/config.json`; raises `FileNotFoundError` with helpful message if missing

### `tables.py`
- `get_table(name: str) -> list[dict]`
- Prod mode: calls `GET /api/v1/tables?name={name}` then `GET /api/v1/tables/{id}/rows` via `client.py`
- Dev mode: reads `./conduit_fixtures/{name}.json`

### `logging.py`
- `log_api_call(method: str, url: str, status_code: int, duration_ms: int, metadata: dict | None = None) -> None`
- Prod mode: posts to `POST /api/v1/internal/log-api-call` with execution_id in header
- Dev mode: prints formatted line to stdout

### `client.py`
- `ConduitClient` — thin `httpx.Client` wrapper
- Base URL: `http://localhost:8000` (configurable via `CONDUIT_BASE_URL`)
- Sets `X-Execution-ID` header from `--conduit-execution-id` arg

### `fixtures.py`
- `load_fixture(name: str) -> list[dict]` — reads `./conduit_fixtures/{name}.json`
- Raises clear error: `"Fixture '{name}.json' not found. Run: conduit export-fixtures --table {name}"`

### `cli.py`
- `conduit` command group (via `click`)
- `conduit export-fixtures --account-id <id> --output <dir>` — calls platform API, writes JSON files
- `conduit export-fixtures --table <name>` — exports single table

### `setup.py`
```python
setup(
    name="conduit-helper",
    version="0.1.0",
    packages=["conduit"],
    install_requires=["httpx>=0.27.0", "click>=8.0.0"],
    entry_points={"console_scripts": ["conduit=cli:cli"]},
)
```

### Success Metrics
- [ ] `pip install -e helper/` succeeds
- [ ] `from conduit import get_config, get_table, log_api_call` — imports without error
- [ ] Dev mode: `CONDUIT_DEV_MODE=1 python -c "from conduit import get_config; print(get_config())"` — prints helpful error about missing fixture (not a crash)
- [ ] Dev mode: with `./conduit_fixtures/config.json` present, `get_config()` returns its contents
- [ ] `python -c "import conduit; print(conduit.__all__)"` prints `['get_config', 'get_table', 'log_api_call']`
- [ ] `conduit --help` shows available commands
- [ ] `conduit export-fixtures --help` shows options

---

## Step 9 — Example Scripts

Working, runnable examples that double as integration tests and developer docs.

### Files to create
- `examples/01_hello_world/script.py`
- `examples/02_using_config/script.py` + `examples/02_using_config/conduit_fixtures/config.json` (sample: `{"API_KEY": "demo-key", "ENV": "dev"}`)
- `examples/03_reading_tables/script.py` + `examples/03_reading_tables/conduit_fixtures/example_data.json`
- `examples/04_writing_tables/script.py` + `examples/04_writing_tables/conduit_fixtures/example_data.json`
- `examples/05_api_logging/script.py` + `examples/05_api_logging/conduit_fixtures/config.json`

### Each script must
- Import from `conduit`
- Work in dev mode (`CONDUIT_DEV_MODE=1`)
- Have a docstring explaining what it demonstrates
- Have a `conduit_fixtures/` folder with sample data where needed

### Success Metrics
- [ ] `cd examples/01_hello_world && CONDUIT_DEV_MODE=1 python script.py` — exits 0, prints output
- [ ] `cd examples/02_using_config && CONDUIT_DEV_MODE=1 python script.py` — reads config, prints a key
- [ ] `cd examples/03_reading_tables && CONDUIT_DEV_MODE=1 python script.py` — iterates rows, prints count
- [ ] All 5 scripts exit with code 0 in dev mode

---

## Step 10 — Integration Smoke Test

Full end-to-end run against a live server.

### Procedure
1. `cd backend && uvicorn app.main:app` — start server
2. `POST /api/v1/accounts` — create account `"Acme Corp"`
3. `POST /api/v1/variables` — create variable `API_KEY = "test-key-123"` (not secret)
4. `POST /api/v1/scripts` — create script with scope `global`, pointing to `examples/01_hello_world/script.py`
5. `POST /api/v1/scripts/{id}/run` — trigger run
6. Poll `GET /api/v1/executions/{id}` until `status != "running"`
7. `GET /api/v1/executions/{id}/logs` — verify stdout logs present
8. `POST /api/v1/cron-jobs` — create a job for the script with `"* * * * *"` (every minute)
9. Wait 60 seconds — verify a new execution row appears automatically
10. `DELETE /api/v1/cron-jobs/{id}` — remove the job
11. `POST /api/v1/internal/log-api-call` with header `X-Execution-ID: <prior_execution_id>` and body `{"method":"GET","url":"https://example.com","status_code":200,"duration_ms":12}` — verify `ExecutionLog(stream="api")` row exists for that execution
12. Start a long-running script (e.g. `time.sleep(60)`), then stop the server while it's running. Restart the server. Verify the corresponding `Execution` row is now `interrupted`.

### Success Metrics
- [ ] Steps 1–7 complete without HTTP errors
- [ ] Execution status is `"success"` after run
- [ ] Stdout logs contain expected output
- [ ] Cron job triggers at least one automatic execution within 2 minutes
- [ ] `GET /api/v1/health` shows `active_scripts: 0` after all runs complete
- [ ] No temp config files remain in `data/tmp/` after runs complete
- [ ] `data/.secret_key` file mode is `600`
- [ ] Internal log endpoint round-trips and produces a stream=`api` log row
- [ ] Run interrupted by server stop is visible as `status="interrupted"` after restart

---

## Post-Build Checklist

After all steps complete and metrics are met:

- [ ] Update `instructions.md` §1 Status: `"Iteration 1 complete. Backend foundation built."`
- [ ] Update `instructions.md` §15 Iteration Log with date and summary
- [ ] Note any new patterns, gotchas, or changed decisions in `instructions.md`
- [ ] Confirm `data/` is gitignored
- [ ] Confirm `.env` is gitignored
- [ ] Tag the build: `git tag v0.1.0-backend-foundation`

---

## Deferred to Iteration 2

Do not build these now:

- React + Vite frontend
- Installer scripts (`install.sh`, `install.ps1`, `install.py`)
- Login / auth implementation
- Per-script virtual environments
- Docker isolation
- Alembic migrations (Iteration 1 uses `Base.metadata.create_all`)
- In-app Settings page (concurrency limit, thresholds — env-only in Iteration 1)
- In-app Docs page
- Webhook trigger ingest endpoint
- Audit log for admin actions
- Backup / restore tooling
