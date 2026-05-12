# Multi-stage build for Conduit — backend + frontend in one container
# Stage 1: Build frontend assets
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Final image — Python + Node runtime
FROM python:3.11-slim
LABEL maintainer="Conduit"
LABEL description="Conduit — self-hosted Python automation platform with UI"

# Install system dependencies (git for script execution, nodejs for runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy backend code
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy entire backend
COPY backend/ ./backend/

# Copy helper package
COPY helper/ ./helper/
RUN pip install -e ./helper/

# Copy frontend build output
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy Docker entrypoint script
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Copy examples (optional, for reference)
COPY examples/ ./examples/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data
ENV DATABASE_URL=sqlite:////data/conduit.db
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000

# Create data directory
RUN mkdir -p /data

# Expose ports
EXPOSE 8000 5173

# Non-root user for security
RUN useradd -m -u 1000 conduit && chown -R conduit:conduit /app /data
USER conduit

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint: run backend (frontend is pre-built and served as static files)
ENTRYPOINT ["./docker-entrypoint.sh"]
