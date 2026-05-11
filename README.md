# Conduit

A self-hosted Python automation platform. Write scripts, run them on a schedule or on demand, manage secrets, share data between scripts, and monitor everything from a web UI.

**Core idea:** the platform handles infrastructure. Your scripts handle the work.

---

## What it does

- **Run Python scripts** on a cron schedule or manually from the UI
- **Inject secrets** — encrypted variables are decrypted and passed to scripts at run time; scripts never manage credentials directly
- **InfoTables** — structured data stores scripts can read and write, visible in the UI as a spreadsheet
- **Supporting Tools** — shared Python modules any script can import (no copy-pasting utility code)
- **Execution history** — every run is logged with stdout, stderr, and outbound API call records
- **System monitoring** — CPU, memory, disk, and queue metrics with configurable alert thresholds
- **Multi-tenant** — resources are scoped globally or to an Account

---

## Requirements

- Python 3.9+
- Node.js 18+
- ~200 MB disk space for the application (runtime data is separate)

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/heyitsmiike101/Conduit.git
cd conduit
```

### 2. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure environment (optional)

The platform works out of the box with no configuration. To customise:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — all fields are optional, defaults are sensible
```

### 4. Start the backend

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The first time it runs, Conduit will:
- Create the SQLite database at `data/conduit.db`
- Generate an encryption key at `data/.secret_key` (mode 600)
- Start the scheduler and metrics collector

You should see:
```
Conduit platform ready
```

### 5. Install frontend dependencies

In a new terminal:

```bash
cd frontend
npm install
```

### 6. Start the frontend

```bash
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Setting up authentication

Authentication is **off by default** — the platform is open, which is fine for local use. To enable it:

**Step 1** — Create the admin account (one-time setup):

```bash
curl -X POST http://localhost:8000/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

**Step 2** — Enable auth in `backend/.env`:

```bash
AUTH_ENABLED=true
JWT_SECRET=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
```

**Step 3** — Restart the backend. All API requests now require a Bearer token.

**Log in:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

Returns `{ "token": "..." }` — include it as `Authorization: Bearer <token>` on subsequent requests.

---

## Writing your first script

### 1. Install the helper library

```bash
cd helper
pip install -e .
```

### 2. Create a script in the UI

Go to **Scripts → New Script**, give it a name, and click Create. A starter `script.py` is generated automatically.

### 3. Edit the code

The Script Detail page has a Monaco editor (VS Code's engine). The helper library gives your script access to config, tables, and logging:

```python
from conduit import get_config, get_table, log_api_call

# Decrypted variables injected at run time
config = get_config()
api_key = config.get("MY_API_KEY")

# Read/write shared data tables
customers = get_table("customer-table-id")
for row in customers.get_rows():
    print(row["name"])

# Log outbound HTTP calls to the execution record
log_api_call(method="GET", url="https://api.example.com/data", status_code=200, duration_ms=145)
```

### 4. Run it

Click **Run Now** on the script page, or set a **Cron Job** to run it automatically.

---

## Developing scripts locally

Use dev mode to run scripts on your machine without a Conduit server:

```bash
export CONDUIT_DEV_MODE=1

# Create fixture files the helper will read from
mkdir conduit_fixtures
echo '{"MY_API_KEY": "dev-key", "ENV": "dev"}' > conduit_fixtures/config.json

python3 my_script.py
```

In dev mode:
- `get_config()` reads from `./conduit_fixtures/config.json`
- `get_table(id)` reads from `./conduit_fixtures/<id>.json`
- `log_api_call()` prints to stdout instead of calling the platform

See the `examples/` directory for five working sample scripts.

---

## Project structure

```
conduit/
├── backend/               # FastAPI app — Python 3.9+
│   ├── app/
│   │   ├── api/           # Route handlers (one file per resource)
│   │   ├── core/          # Config, security, encryption
│   │   ├── db/            # SQLAlchemy models and session
│   │   ├── middleware/    # Rate limiting, request size limits
│   │   ├── services/      # Business logic (runner, scheduler, metrics, audit)
│   │   └── main.py        # App entrypoint and lifespan
│   ├── .env.example       # All available environment variables
│   └── requirements.txt
├── frontend/              # React + Vite — Node 18+
│   └── src/
│       ├── api/           # API client (one file per resource)
│       ├── components/    # Reusable UI components
│       └── pages/         # Route-level pages
├── helper/                # conduit-helper pip package
│   └── conduit/           # get_config, get_table, log_api_call, run_script
├── examples/              # Five working sample scripts with fixtures
└── data/                  # Runtime data — gitignored
    ├── conduit.db         # SQLite database
    ├── .secret_key        # Fernet encryption key (chmod 600)
    ├── scripts/           # Script files on disk
    └── logs/
```

---

## Configuration reference

All settings are optional. Set them in `backend/.env` or as environment variables.

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `<repo>/data/` | Where the DB, scripts, and logs are stored |
| `DATABASE_URL` | SQLite in DATA_DIR | SQLAlchemy connection string |
| `MAX_CONCURRENT_SCRIPTS` | `10` | Max scripts running in parallel |
| `METRICS_INTERVAL_SECONDS` | `30` | How often system metrics are sampled |
| `WARN_THRESHOLD` | `0.75` | CPU/memory/disk fraction that triggers a warning |
| `CRITICAL_THRESHOLD` | `0.90` | Fraction that triggers a critical alert |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated allowed origins |
| `AUTH_ENABLED` | `false` | Require JWT login for all API requests |
| `JWT_SECRET` | auto-generated | Token signing secret — set this in production |
| `JWT_EXPIRY_HOURS` | `24` | How long a token remains valid |
| `ENCRYPTION_KEY` | *(reads from key file)* | Inject Fernet key from a secrets manager |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## API

The full REST API is documented at **http://localhost:8000/docs** (Swagger UI) once the backend is running.

Base path: `/api/v1`

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Platform status and current settings |
| `POST` | `/auth/login` | Get a JWT token |
| `GET` | `/scripts` | List scripts |
| `POST` | `/scripts` | Create a script |
| `POST` | `/executions` | Trigger a script run |
| `GET` | `/executions/{id}/logs` | Stream execution output |
| `GET` | `/variables` | List variables and API keys |
| `GET` | `/tables` | List InfoTables |
| `GET` | `/cron-jobs` | List scheduled jobs |
| `GET` | `/audit-logs` | Audit trail (requires auth) |
| `GET` | `/metrics?hours=24` | Historical system metrics |

---

## Security notes

- Secrets are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256)
- The encryption key lives at `data/.secret_key` (chmod 600, never committed)
- To back up the key or support multi-instance deployments, set `ENCRYPTION_KEY` via env var
- Scripts run as subprocesses with no shell injection (`asyncio.create_subprocess_exec`)
- All file access is path-traversal protected
- SQL uses parameterised queries via SQLAlchemy ORM
- CORS requires explicit origin list — wildcard is blocked when credentials are enabled
- Rate limiting: 60 requests/minute per IP

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, APScheduler |
| Database | SQLite (single-VPS) |
| Encryption | `cryptography` — Fernet |
| Code editor | Monaco (VS Code's engine) |
| Frontend | React, Vite, TanStack Query |
| Scheduling | APScheduler with SQLite jobstore |
| Auth | bcrypt + JWT (PyJWT) |
