#!/bin/sh
# Docker entrypoint for Conduit — runs only the backend
# Frontend is pre-built and served by uvicorn

cd /app/backend

exec python -m uvicorn app.main:app \
    --host "${UVICORN_HOST:-0.0.0.0}" \
    --port "${UVICORN_PORT:-8000}"
