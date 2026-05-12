# Multi-stage build for Conduit — backend + frontend in one container
#
# Stage 1: Build frontend assets (Node stays here — not copied to final image)
FROM node:20-alpine3.21 AS frontend-builder
WORKDIR /app/frontend
# Copy manifests first so npm ci is cached independently of source changes
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime image — Python only (Node is build-time only)
FROM python:3.11-slim-bookworm
LABEL maintainer="Conduit"
LABEL description="Conduit — self-hosted Python automation platform with UI"

# Runtime system deps:
#   git            — available to user scripts at runtime
#   curl           — used by the HEALTHCHECK
#   gosu           — privilege drop in entrypoint (root → conduit) with correct signal forwarding
#   build-essential — required by uvloop (uvicorn[standard]) + cryptography C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies before copying source so this layer is cached
# independently — a code change won't re-run pip install
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application source
COPY backend/ ./backend/
COPY helper/ ./helper/
RUN pip install --no-cache-dir -e ./helper/

# Copy pre-built frontend from Stage 1 (no Node needed in this image)
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy entrypoint and optional examples
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
COPY examples/ ./examples/

# Baked-in defaults — all can be overridden at runtime via environment variables
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    DATABASE_URL=sqlite:////data/conduit.db \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

# Create the app user and /data — ownership of /data is re-applied at runtime
# by the entrypoint so host volume mounts with different ownership still work
RUN mkdir -p /data \
    && useradd -m -u 1000 conduit \
    && chown -R conduit:conduit /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint runs as root so it can fix /data ownership, then drops to conduit
ENTRYPOINT ["./docker-entrypoint.sh"]
