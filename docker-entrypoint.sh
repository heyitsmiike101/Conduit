#!/bin/sh
set -e

# Fix /data ownership if running as root (handles host volume mount permission
# mismatches where the host directory is owned by a different uid than conduit).
# gosu then drops privileges and re-execs this script as the conduit user,
# so the app process itself never runs as root.
if [ "$(id -u)" = "0" ]; then
    chown -R conduit:conduit /data
    exec gosu conduit "$0" "$@"
fi

cd /app/backend
exec python -m uvicorn app.main:app \
    --host "${UVICORN_HOST:-0.0.0.0}" \
    --port "${UVICORN_PORT:-8000}"
