/**
 * Docs — in-app reference documentation for script authors.
 */

import React, { useState } from 'react'

// ─── Data ─────────────────────────────────────────────────────────────────────

const SECTIONS = [
  {
    id: 'overview',
    title: 'Overview',
    content: [
      {
        type: 'prose',
        text: `Conduit is a script-hosting platform. You write Python scripts, upload them through the UI, and the platform handles scheduling, secrets injection, structured logging, and data sharing between scripts via InfoTables.`,
      },
      {
        type: 'prose',
        text: `Scripts communicate with the platform through the conduit-helper library. In development, the helper runs in dev mode — reads config from local fixture files and prints output to stdout instead of making real API calls.`,
      },
    ],
  },
  {
    id: 'quickstart',
    title: 'Quick Start',
    content: [
      { type: 'heading', text: '1. Install conduit-helper' },
      { type: 'code', lang: 'bash', text: `cd helper\npip install -e .` },
      { type: 'heading', text: '2. Write a script' },
      { type: 'code', lang: 'python', text: `from conduit import get_config\n\nconfig = get_config()\nprint(f"Running in: {config.get('ENV', 'unknown')}")` },
      { type: 'heading', text: '3. Run locally (dev mode)' },
      { type: 'code', lang: 'bash', text: `mkdir conduit_fixtures\necho '{"ENV": "dev"}' > conduit_fixtures/config.json\n\nCONDUIT_DEV_MODE=1 python script.py` },
      { type: 'heading', text: '4. Upload and run on the platform' },
      { type: 'prose', text: 'Create a Script in the UI, edit the code in the Monaco editor, save, and click Run Now.' },
    ],
  },
  {
    id: 'scripts',
    title: 'Scripts',
    content: [
      { type: 'prose', text: 'A Script is a Python file (or a folder of files) managed by Conduit. The platform stores its code on disk, tracks its history, and runs it on demand or on a schedule.' },

      { type: 'heading', text: 'Creating a script' },
      { type: 'list', items: [
        'Go to Scripts → New Script.',
        'Give it a name and optional description.',
        'Choose scope: global (shared across all accounts) or account-scoped.',
        'Optionally set a timeout in seconds — the runner will kill the process if it exceeds this.',
        'Click Create Script. A starter script.py is generated automatically on disk.',
      ]},

      { type: 'heading', text: 'Editing code' },
      { type: 'prose', text: 'The Script Detail page has a Monaco code editor (the same engine as VS Code). Every save auto-creates a version snapshot so you can roll back. The yellow dot in the file sidebar means you have unsaved changes in that file.' },

      { type: 'heading', text: 'Multiple files in a script' },
      { type: 'prose', text: 'Each script lives in its own folder on disk. You can add as many supporting files as you want — Python modules, JSON configs, CSVs, even binary assets. Use the file browser on the left of the editor to switch between files, create folders, or drag-and-drop to upload.' },
      { type: 'code', lang: 'text', text: `data/scripts/global/{script-id}/\n  script.py          ← entry point (always present)\n  helpers.py         ← extra module you added\n  data/\n    mapping.json     ← static data file` },
      { type: 'prose', text: 'The entry point is always script.py. Other .py files in the same directory can be imported relative to it:' },
      { type: 'code', lang: 'python', text: `# script.py — import a sibling module\nfrom helpers import process_row\n\nfor row in rows:\n    process_row(row)` },

      { type: 'heading', text: 'Running a script' },
      { type: 'list', items: [
        'Click "Run Now" on the Script Detail or Scripts list page.',
        'Conduit enforces one run per script at a time — a second trigger is rejected if the script is already running or queued.',
        'Set a Cron Job to run a script automatically on a schedule.',
        'Call run_script(script_id) from another script to trigger it programmatically.',
      ]},

      { type: 'heading', text: 'Version history' },
      { type: 'prose', text: 'Every save of script.py creates a numbered snapshot. Open the "Versions" tab on the Script Detail page to browse history and click "Revert" to restore any prior version.' },

      { type: 'heading', text: 'Injected config' },
      { type: 'prose', text: 'Before each run, Conduit writes a temporary config file containing all Variables and API Keys scoped to the script. The conduit-helper get_config() call reads this file — your script never has to manage secrets itself.' },

      { type: 'heading', text: 'File path (on disk)' },
      { type: 'prose', text: 'The physical location of each script is shown on its detail page. Global scripts live under data/scripts/global/, account scripts under data/scripts/accounts/{account_id}/.' },
    ],
  },
  {
    id: 'tools',
    title: 'Supporting Tools',
    content: [
      { type: 'prose', text: 'Supporting Tools are reusable Python modules that live in a shared location on the platform. Every script can import them directly — no copying code between scripts.' },

      { type: 'heading', text: 'When to use a tool vs a script' },
      { type: 'table', headers: ['Use a Script when…', 'Use a Tool when…'], rows: [
        ['You want to run it on a schedule or on demand', 'You want to share helper functions across scripts'],
        ['It produces output or side-effects by itself', 'It only provides utilities, API clients, or data mappers'],
        ['It needs execution history and logs', 'It has no meaningful "entry point" to run'],
      ]},

      { type: 'heading', text: 'Creating a tool' },
      { type: 'list', items: [
        'Go to Tools → New Tool.',
        'Give it a name — Conduit derives the Python import name automatically.',
        'e.g. "Runn API Helper" becomes import runn_api_helper.',
        'Click Create Tool. A starter .py file is generated with example functions.',
        'Edit the file in the Monaco editor, save, and your tool is live immediately.',
      ]},

      { type: 'heading', text: 'Import name' },
      { type: 'prose', text: 'The import name is derived from the tool name: non-alphanumeric characters become underscores, the result is lowercased. The import name is shown on the tool card and its detail page.' },
      { type: 'code', lang: 'text', text: `Tool name       →  Import name\n─────────────────────────────────────\nRunn API Helper →  runn_api_helper\nHTTP Utils      →  http_utils\nMy Company SDK  →  my_company_sdk` },

      { type: 'heading', text: 'Using a tool in a script' },
      { type: 'code', lang: 'python', text: `# Import the whole tool module\nimport runn_api_helper\n\n# Or import specific names\nfrom runn_api_helper import get_client, format_date\n\n# Use it normally\nclient = get_client(api_key="...")\ndata   = client.list_users()` },
      { type: 'prose', text: 'Conduit adds every enabled tool directory to PYTHONPATH before running any script. No extra setup is required — the import just works.' },

      { type: 'heading', text: 'Tool file structure' },
      { type: 'prose', text: 'Each tool has its own folder. The main file is named after the import name. You can add helper files inside the same folder.' },
      { type: 'code', lang: 'text', text: `data/tools/{tool-id}/\n  runn_api_helper.py   ← main file (importable as runn_api_helper)\n  models.py            ← supporting file (import as models from within the tool)\n  fixtures/\n    test_data.json` },

      { type: 'heading', text: 'Writing a tool' },
      { type: 'code', lang: 'python', text: `# runn_api_helper.py\n"""\nRunn API client helper.\nImport in scripts:  from runn_api_helper import get_client\n"""\nimport requests\n\nBASE_URL = "https://api.runn.io/v1"\n\n\nclass RunnClient:\n    def __init__(self, api_key: str):\n        self.session = requests.Session()\n        self.session.headers["Authorization"] = f"Bearer {api_key}"\n\n    def list_projects(self):\n        return self.session.get(f"{BASE_URL}/projects").json()\n\n    def get_person(self, person_id: str):\n        return self.session.get(f"{BASE_URL}/people/{person_id}").json()\n\n\ndef get_client(api_key: str) -> RunnClient:\n    """Convenience factory — pass the API key from get_config()."""\n    return RunnClient(api_key)` },

      { type: 'heading', text: 'Using a tool with config' },
      { type: 'code', lang: 'python', text: `# script.py — typical usage pattern\nfrom conduit import get_config\nfrom runn_api_helper import get_client\n\nconfig = get_config()\nclient = get_client(api_key=config["RUNN_API_KEY"])\n\nprojects = client.list_projects()\nfor p in projects:\n    print(p["name"])` },

      { type: 'heading', text: 'Disabling a tool' },
      { type: 'prose', text: 'Toggling the enabled switch on a tool stops Conduit from adding it to PYTHONPATH. Scripts that import it will fail at run time with an ImportError until the tool is re-enabled.' },

      { type: 'heading', text: 'Multiple files in a tool' },
      { type: 'prose', text: 'You can add extra .py files inside the tool folder. Import them within the tool using standard relative imports, or reference them by filename from within the same directory (since the tool dir is on PYTHONPATH).' },
      { type: 'code', lang: 'python', text: `# In runn_api_helper.py — import a sibling file\nfrom models import Project, Person  # models.py in the same tool folder` },
    ],
  },
  {
    id: 'helper-api',
    title: 'conduit-helper API',
    content: [
      { type: 'heading', text: 'get_config()' },
      { type: 'code', lang: 'python', text: `from conduit import get_config\n\nconfig = get_config()\n# Returns a dict of key → value for all Variables and API Keys\n# injected at run time (global scope + account scope merged).\n# In dev mode, reads from ./conduit_fixtures/config.json.\n\napi_key = config.get("MY_API_KEY", "")` },
      { type: 'heading', text: 'get_table(table_id)' },
      { type: 'code', lang: 'python', text: `from conduit import get_table\n\ntbl = get_table("my-table-id")\n\n# Read rows\nrows = tbl.get_rows()         # list of dicts\nfor row in rows:\n    print(row["name"], row["score"])\n\n# Write a row\ntbl.insert_row({"name": "Alice", "score": 95})\n\n# Update a row\ntbl.update_row(row_id="<uuid>", data={"score": 97})\n\n# Delete a row\ntbl.delete_row(row_id="<uuid>")` },
      { type: 'prose', text: 'In dev mode, get_rows() reads from ./conduit_fixtures/<table_id>.json. Writes print to stdout but are not persisted to disk.' },
      { type: 'heading', text: 'log_api_call(method, url, status_code, duration_ms, metadata=None)' },
      { type: 'code', lang: 'python', text: `import time, requests\nfrom conduit import log_api_call\n\nstart = time.time()\nresp  = requests.get("https://api.example.com/data")\nms    = (time.time() - start) * 1000\n\nlog_api_call(\n    method="GET",\n    url="https://api.example.com/data",\n    status_code=resp.status_code,\n    duration_ms=ms,\n)\n# Appears in the Execution log stream (visible in the UI).\n# In dev mode, prints to stdout.` },
      { type: 'heading', text: 'run_script(script_id)' },
      { type: 'code', lang: 'python', text: `from conduit import run_script\n\n# Trigger another Conduit script asynchronously.\n# Returns immediately — does not wait for the triggered script to finish.\nresult = run_script("target-script-uuid")\nprint(f"Triggered: {result['execution_id']}")\n\n# In dev mode, prints to stdout and returns a placeholder.` },
    ],
  },
  {
    id: 'dev-mode',
    title: 'Dev Mode',
    content: [
      { type: 'prose', text: 'Set CONDUIT_DEV_MODE=1 to run scripts locally without a running Conduit server. The helper switches to file-based fixtures and stdout logging.' },
      { type: 'heading', text: 'Fixture files' },
      { type: 'code', lang: 'text', text: `your-script/\n  script.py\n  conduit_fixtures/\n    config.json          ← returned by get_config()\n    <table-id>.json      ← returned by get_table(id).get_rows()` },
      { type: 'heading', text: 'Example config.json' },
      { type: 'code', lang: 'json', text: `{\n  "MY_API_KEY": "sk-dev-key",\n  "ENV": "dev",\n  "BASE_URL": "https://api.example.com"\n}` },
      { type: 'heading', text: 'Example table fixture' },
      { type: 'code', lang: 'json', text: `[\n  {"name": "Alice", "score": 95},\n  {"name": "Bob",   "score": 87}\n]` },
    ],
  },
  {
    id: 'variables',
    title: 'Variables & API Keys',
    content: [
      { type: 'prose', text: 'Variables and API keys are encrypted at rest and injected into every script run as the config dict returned by get_config().' },
      { type: 'heading', text: 'Config Variables' },
      { type: 'prose', text: 'Key/value pairs for settings like URLs, feature flags, and non-sensitive config. Can optionally be marked secret (masked in UI, revealable for 5 seconds). Editable after creation.' },
      { type: 'heading', text: 'API Keys' },
      { type: 'prose', text: 'Write-only credentials. The value is encrypted on save and can never be viewed again through the UI. To rotate a key, delete it and create a new one.' },
      { type: 'heading', text: 'Scope' },
      { type: 'list', items: [
        'global — available to all scripts on the platform.',
        'account — available only to scripts under the same account. Account-scoped values override global ones with the same name.',
      ]},
      { type: 'heading', text: 'Viewing injected config per script' },
      { type: 'prose', text: 'On the Script Detail page, expand "Injected Config" to see exactly which variables and API keys will be available to that script at run time.' },
    ],
  },
  {
    id: 'tables',
    title: 'InfoTables',
    content: [
      { type: 'prose', text: 'InfoTables are structured, row-based data stores that any script can read and write. Think of them as lightweight database tables shared across your entire script ecosystem.' },

      { type: 'heading', text: 'Creating a table' },
      { type: 'prose', text: 'Create tables in the UI under Tables → New Table. Give it a name and optional column schema. The table ID shown on the detail page is what you pass to get_table().' },

      { type: 'heading', text: 'get_table(table_id)' },
      { type: 'code', lang: 'python', text: `from conduit import get_table\n\ntbl = get_table("your-table-id-here")` },
      { type: 'prose', text: 'Returns a Table object. The table ID is the UUID shown on the table detail page (not the name). In dev mode, reads/writes use local fixture files.' },

      { type: 'heading', text: 'Reading rows — get_rows()' },
      { type: 'code', lang: 'python', text: `from conduit import get_table\n\ntbl = get_table("abc-123")\n\n# Returns a list of dicts — one per row\nrows = tbl.get_rows()\n# => [\n#   {"id": "row-uuid", "name": "Alice", "score": 95},\n#   {"id": "row-uuid", "name": "Bob",   "score": 87},\n# ]\n\n# Each row dict includes the special "id" key (the row UUID)\nfor row in rows:\n    print(f"{row['name']}: {row['score']}")\n\n# Filter in Python (no server-side filter yet)\nhigh_scores = [r for r in rows if r.get("score", 0) >= 90]` },

      { type: 'heading', text: 'Adding a row — insert_row(data)' },
      { type: 'code', lang: 'python', text: `from conduit import get_table\n\ntbl = get_table("abc-123")\n\n# Pass any dict — keys become columns\nnew_row = tbl.insert_row({\n    "name":  "Charlie",\n    "email": "charlie@example.com",\n    "score": 92,\n    "tags":  "beta,vip",    # store lists as comma-separated strings\n})\n\nprint(f"Created row: {new_row['id']}")\n\n# Columns not yet in the schema appear automatically in the UI` },

      { type: 'heading', text: 'Updating a row — update_row(row_id, data)' },
      { type: 'code', lang: 'python', text: `from conduit import get_table\n\ntbl = get_table("abc-123")\nrows = tbl.get_rows()\n\n# Find the row you want\nalice = next((r for r in rows if r["name"] == "Alice"), None)\nif alice:\n    # Pass only the fields you want to change\n    # Unspecified fields are preserved\n    tbl.update_row(\n        row_id=alice["id"],\n        data={"score": 99, "status": "champion"},\n    )\n    print("Updated Alice's score")` },

      { type: 'heading', text: 'Deleting a row — delete_row(row_id)' },
      { type: 'code', lang: 'python', text: `from conduit import get_table\n\ntbl = get_table("abc-123")\nrows = tbl.get_rows()\n\n# Delete one row by ID\ntbl.delete_row(row_id=rows[0]["id"])\n\n# Delete all rows matching a condition\nexpired = [r for r in rows if r.get("status") == "expired"]\nfor row in expired:\n    tbl.delete_row(row_id=row["id"])\nprint(f"Purged {len(expired)} expired rows")` },

      { type: 'heading', text: 'Full example — accumulate run history' },
      { type: 'code', lang: 'python', text: `"""\nCron script that records its own run stats each time it fires.\nTable: run_log  columns: [run_at, duration_s, rows_processed, status]\n"""\nimport time\nfrom datetime import datetime, timezone\nfrom conduit import get_config, get_table\n\nconfig = get_config()\ntbl    = get_table("run-log-table-id")\n\nstart = time.time()\nstatus = "ok"\ntry:\n    # ... your automation logic here ...\n    rows_processed = 42\nexcept Exception as e:\n    rows_processed = 0\n    status = f"error: {e}"\nfinally:\n    tbl.insert_row({\n        "run_at":         datetime.now(timezone.utc).isoformat(),\n        "duration_s":     round(time.time() - start, 2),\n        "rows_processed": rows_processed,\n        "status":         status,\n    })` },

      { type: 'heading', text: 'Full example — work queue between two scripts' },
      { type: 'code', lang: 'python', text: `# ── enqueuer.py ──────────────────────────────────────────────────\nfrom conduit import get_table, run_script\n\nqueue = get_table("work-queue-id")\n\n# Add items for the processor to handle\nfor url in ["https://a.com", "https://b.com", "https://c.com"]:\n    queue.insert_row({"url": url, "status": "pending"})\n\n# Wake up the processor\nrun_script("processor-script-uuid")\n\n\n# ── processor.py ─────────────────────────────────────────────────\nfrom conduit import get_table\nimport requests\n\nqueue = get_table("work-queue-id")\npending = [r for r in queue.get_rows() if r["status"] == "pending"]\n\nfor item in pending:\n    try:\n        requests.get(item["url"], timeout=10)\n        queue.update_row(item["id"], {"status": "done"})\n    except Exception as e:\n        queue.update_row(item["id"], {"status": f"failed: {e}"})` },

      { type: 'heading', text: 'Dev mode fixtures' },
      { type: 'prose', text: 'When CONDUIT_DEV_MODE=1, get_table() reads rows from a local JSON file at ./conduit_fixtures/<table_id>.json. Writes print to stdout but are not persisted to disk.' },
      { type: 'code', lang: 'json', text: `// conduit_fixtures/abc-123.json\n[\n  {"id": "row-1", "name": "Alice", "score": 95},\n  {"id": "row-2", "name": "Bob",   "score": 87}\n]` },

      { type: 'heading', text: 'Tips & patterns' },
      { type: 'list', items: [
        'Use a "status" column ("pending" / "done" / "failed") to build reliable work queues.',
        'Store timestamps as ISO-8601 strings (datetime.utcnow().isoformat()) for easy sorting.',
        'Dedup before inserting: call get_rows(), check if item exists, then insert_row() only if not found.',
        'Numeric values (int, float) are stored as JSON numbers and come back as Python int/float — no casting needed.',
        'Each row always has an "id" key (UUID string). Do not include "id" in insert_row() — it is assigned by the server.',
        'There is no server-side filter yet — fetch all rows and filter in Python.',
      ]},
    ],
  },
  {
    id: 'cron',
    title: 'Cron Scheduling',
    content: [
      { type: 'prose', text: 'Any script can be scheduled on a cron expression. Schedules are managed in the Cron Jobs section. Use the built-in cron builder or type an expression directly. Each schedule has an optional name and description to remind you what it does.' },
      { type: 'heading', text: 'Name & description' },
      { type: 'prose', text: 'Give each schedule a friendly name (e.g. "Daily report sync") and a short description. Without a name the schedule shows the script name. Descriptions appear below the name in the list.' },
      { type: 'heading', text: 'Expression format' },
      { type: 'code', lang: 'text', text: `┌─────────── minute (0-59)\n│ ┌───────── hour (0-23)\n│ │ ┌─────── day of month (1-31)\n│ │ │ ┌───── month (1-12)\n│ │ │ │ ┌─── day of week (0=Sun, 6=Sat)\n│ │ │ │ │\n* * * * *` },
      { type: 'heading', text: 'Common expressions' },
      { type: 'table', headers: ['Expression', 'Meaning'], rows: [
        ['* * * * *',       'Every minute'],
        ['*/5 * * * *',     'Every 5 minutes'],
        ['0 * * * *',       'Every hour'],
        ['0 0 * * *',       'Daily at midnight UTC'],
        ['0 9 * * *',       'Daily at 9 AM UTC'],
        ['0 9 * * 1-5',     'Weekdays at 9 AM UTC'],
        ['0 9 * * 1',       'Every Monday at 9 AM'],
        ['0 */6 * * *',     'Every 6 hours'],
        ['0 0 1 * *',       'First of every month'],
        ['30 8 * * 1-5',    'Weekdays at 8:30 AM'],
      ]},
      { type: 'prose', text: 'Wildcards: * = any value · */n = every n · n-m = range · n,m = list of values.' },
    ],
  },
  {
    id: 'script-to-script',
    title: 'Script-to-Script',
    content: [
      { type: 'prose', text: 'Scripts can trigger other scripts via run_script(). The triggered script is queued as a new independent execution — the caller does not wait for it to finish.' },
      { type: 'code', lang: 'python', text: `from conduit import get_config, get_table, run_script\n\nconfig = get_config()\ntbl = get_table("work-queue-table-id")\n\n# Add a work item\ntbl.insert_row({"url": "https://example.com", "priority": "high"})\n\n# Hand off to the processor script\nresult = run_script("processor-script-uuid")\nprint(f"Processor queued: {result['execution_id']}")` },
      { type: 'prose', text: 'A common pattern: an "enqueuer" script writes items to an InfoTable then calls run_script() to wake up a "processor" script that reads and processes the queue.' },
      { type: 'prose', text: 'In dev mode, run_script() prints to stdout and returns a placeholder dict without making any API call.' },
    ],
  },
  {
    id: 'executions',
    title: 'Executions',
    content: [
      { type: 'prose', text: 'Each script run creates an Execution record. View execution output and status on the Script Detail page.' },
      { type: 'table', headers: ['Status', 'Description'], rows: [
        ['queued',      'Waiting for a concurrency slot.'],
        ['running',     'Process is active. Logs stream in real time.'],
        ['success',     'Script exited with code 0.'],
        ['failed',      'Script exited with non-zero code or raised an exception.'],
        ['cancelled',   'Cancelled via the UI.'],
        ['interrupted', 'Server was restarted while the script was running.'],
        ['timeout',     'Script exceeded its timeout_seconds limit.'],
      ]},
      { type: 'prose', text: 'stdout, stderr, and API call logs all appear in the execution log panel. Click any execution row to expand its output.' },
    ],
  },
  {
    id: 'api',
    title: 'REST API',
    content: [
      { type: 'prose', text: 'All endpoints are under /api/v1. The API returns JSON and uses standard HTTP status codes. Interactive docs at /docs (Swagger UI).' },
      { type: 'table', headers: ['Method', 'Path', 'Description'], rows: [
        ['GET',    '/health',                              'Platform health + current settings'],
        ['GET',    '/settings',                            'Get mutable settings'],
        ['PATCH',  '/settings',                            'Update settings (live, persisted)'],
        ['GET',    '/metrics?hours=24',                    'Historical system metrics'],
        ['GET',    '/accounts',                            'List accounts'],
        ['POST',   '/accounts',                            'Create account'],
        ['GET',    '/scripts',                             'List scripts'],
        ['POST',   '/scripts',                             'Create script'],
        ['GET',    '/scripts/{id}/content',               'Read script file from disk'],
        ['PUT',    '/scripts/{id}/content',               'Save code + auto-version'],
        ['GET',    '/scripts/{id}/versions',              'List version history'],
        ['POST',   '/scripts/{id}/versions/{vid}/revert', 'Revert to a prior version'],
        ['GET',    '/scripts/{id}/config',                'Variables injected into this script'],
        ['POST',   '/executions',                          'Trigger a script run'],
        ['GET',    '/executions/{id}/logs',               'Get execution logs'],
        ['POST',   '/executions/{id}/cancel',             'Cancel a running execution'],
        ['GET',    '/variables',                           'List variables + API keys'],
        ['POST',   '/variables',                           'Create variable or API key'],
        ['PATCH',  '/variables/{id}',                     'Edit variable name/value'],
        ['GET',    '/tables',                              'List InfoTables'],
        ['POST',   '/tables',                              'Create table'],
        ['GET',    '/tables/{id}/rows',                   'List rows'],
        ['POST',   '/tables/{id}/rows',                   'Insert row'],
        ['PATCH',  '/tables/{id}/rows/{row_id}',          'Update row'],
        ['DELETE', '/tables/{id}/rows/{row_id}',          'Delete row'],
        ['GET',    '/cron-jobs',                           'List schedules'],
        ['POST',   '/cron-jobs',                           'Create schedule'],
        ['POST',   '/cron-jobs/{id}/pause',               'Pause schedule'],
        ['POST',   '/cron-jobs/{id}/resume',              'Resume schedule'],
        ['GET',    '/notifications',                       'List notifications'],
        ['POST',   '/notifications/dismiss-all',          'Dismiss all notifications'],
        ['POST',   '/notifications/{id}/dismiss',         'Dismiss one notification'],
      ]},
      { type: 'heading', text: 'Internal endpoints (called by conduit-helper)' },
      { type: 'table', headers: ['Method', 'Path', 'Description'], rows: [
        ['POST', '/internal/log-api-call',    'Record outbound HTTP call. Requires X-Execution-ID.'],
        ['POST', '/internal/trigger-script',  'Queue another script. Requires X-Execution-ID.'],
      ]},
    ],
  },
]

// ─── Renderers ────────────────────────────────────────────────────────────────

function CodeBlock({ lang, text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) })
  }
  return (
    <div className="relative group">
      {lang && <span className="absolute top-2 left-3 text-xs text-gray-700 font-mono z-10">{lang}</span>}
      <pre className="bg-gray-950 border border-gray-800 rounded-lg px-4 pt-7 pb-4 overflow-x-auto text-xs font-mono text-gray-300 leading-relaxed">
        {text}
      </pre>
      <button
        onClick={copy}
        className="absolute top-2 right-2 text-xs px-2 py-0.5 bg-gray-800 hover:bg-gray-700 text-gray-400 rounded opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {copied ? '✓ Copied' : 'Copy'}
      </button>
    </div>
  )
}

function DocTable({ headers, rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800">
            {headers.map(h => <th key={h} className="text-left text-xs font-medium text-gray-500 py-2 pr-4">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-gray-800/50 last:border-0">
              {row.map((cell, j) => (
                <td key={j} className="py-2 pr-4 text-gray-400 align-top">
                  <code className="font-mono text-xs text-gray-300">{cell}</code>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function renderBlock(block, i) {
  switch (block.type) {
    case 'prose':   return <p key={i} className="text-sm text-gray-400 leading-relaxed">{block.text}</p>
    case 'heading': return <h3 key={i} className="text-sm font-semibold text-gray-200 pt-2">{block.text}</h3>
    case 'code':    return <CodeBlock key={i} lang={block.lang} text={block.text} />
    case 'list':    return <ul key={i} className="space-y-1 pl-4">{block.items.map((item, j) => <li key={j} className="text-sm text-gray-400 list-disc leading-relaxed">{item}</li>)}</ul>
    case 'table':   return <DocTable key={i} headers={block.headers} rows={block.rows} />
    default:        return null
  }
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function Docs() {
  const [activeId, setActiveId] = useState('overview')
  const activeSection = SECTIONS.find(s => s.id === activeId)
  const activeIndex = SECTIONS.findIndex(s => s.id === activeId)

  return (
    <div className="flex gap-6 min-h-0">
      {/* Sidebar TOC */}
      <nav className="w-44 shrink-0">
        <div className="card p-3 sticky top-4">
          <div className="text-xs font-medium text-gray-600 uppercase tracking-wider mb-2 px-2">Contents</div>
          <ul className="space-y-0.5">
            {SECTIONS.map(s => (
              <li key={s.id}>
                <button
                  onClick={() => setActiveId(s.id)}
                  className={`w-full text-left text-sm px-2 py-1.5 rounded transition-colors ${
                    activeId === s.id
                      ? 'text-brand-300 bg-brand-900/30'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                  }`}
                >
                  {s.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div>
          <h1 className="text-2xl font-semibold text-white">{activeSection.title}</h1>
          <div className="w-12 h-0.5 bg-brand-500 mt-2 mb-6 rounded-full" />
        </div>

        <div className="space-y-4">
          {activeSection.content.map((block, i) => renderBlock(block, i))}
        </div>

        <div className="flex justify-between mt-10 pt-6 border-t border-gray-800">
          {activeIndex > 0 ? (
            <button className="btn-ghost text-sm" onClick={() => setActiveId(SECTIONS[activeIndex - 1].id)}>
              ← {SECTIONS[activeIndex - 1].title}
            </button>
          ) : <span />}
          {activeIndex < SECTIONS.length - 1 ? (
            <button className="btn-ghost text-sm" onClick={() => setActiveId(SECTIONS[activeIndex + 1].id)}>
              {SECTIONS[activeIndex + 1].title} →
            </button>
          ) : <span />}
        </div>
      </div>
    </div>
  )
}
