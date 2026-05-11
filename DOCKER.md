# Conduit Docker Deployment

Run Conduit in a Docker container with persistent data storage.

## Quick Start (30 seconds)

```bash
# Clone and navigate to repo
git clone https://github.com/heyitsmiike101/Conduit.git
cd Conduit

# Start Conduit with Docker Compose
docker-compose up -d

# Access the app
# Backend:  http://localhost:8000
# Frontend: http://localhost:5173
```

Data is automatically persisted to `./conduit-data/` on your machine.

---

## Configuration

### 1. **Persistent Data Directory** (Required)

By default, Conduit stores all data in `./conduit-data/` (relative to where you run `docker-compose`).

To use a custom directory:

```bash
# Set environment variable before running docker-compose
export DATA_DIR_HOST=/mnt/storage/conduit-data
docker-compose up -d
```

**Example configurations:**

```bash
# 1. Local development (creates conduit-data/ in current folder)
export DATA_DIR_HOST=./conduit-data
docker-compose up -d

# 2. Absolute path (e.g., external drive on macOS)
export DATA_DIR_HOST=/Volumes/ExternalDrive/conduit-data
docker-compose up -d

# 3. Network storage (NFS, Samba, etc.)
export DATA_DIR_HOST=/mnt/nfs/conduit-data
docker-compose up -d

# 4. Docker volume (Docker-managed, not host-mounted)
# Edit docker-compose.yml, uncomment volumes section and use volume mount instead
```

### 2. **Environment Configuration**

Copy `.env.docker.example` to `.env` and customize:

```bash
cp .env.docker.example .env
# Edit .env with your settings
docker-compose up -d
```

**Key variables:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATA_DIR_HOST` | `./conduit-data` | Host directory for persistent data |
| `BACKEND_PORT` | `8000` | Backend API port |
| `FRONTEND_PORT` | `5173` | Frontend dev server port |
| `MAX_CONCURRENT_SCRIPTS` | `10` | Max parallel script executions |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `AUTH_ENABLED` | `false` | Enable authentication (dev: false, prod: true) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | CORS whitelist |

---

## Common Tasks

### View Logs

```bash
# Follow logs from the running container
docker-compose logs -f conduit

# View last 100 lines
docker-compose logs --tail=100 conduit
```

### Stop & Start

```bash
# Stop the container (data is preserved)
docker-compose down

# Start again (resumes from where it stopped)
docker-compose up -d
```

### Backup Data

```bash
# Copy the persistent data directory
cp -r conduit-data /backup/conduit-data-$(date +%Y%m%d)

# Or from mounted directory:
cp -r /mnt/storage/conduit-data /backup/conduit-data-$(date +%Y%m%d)
```

### Restart After Update

```bash
# Pull latest changes from GitHub
git pull origin main

# Rebuild the Docker image
docker-compose build --no-cache

# Start with new image
docker-compose up -d
```

### Access Container Shell

```bash
# Useful for debugging
docker-compose exec conduit /bin/bash
```

---

## Advanced Configuration

### Resource Limits

Edit `docker-compose.yml` to set CPU and memory limits:

```yaml
services:
  conduit:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Custom Ports

If port 8000 or 5173 are already in use:

```bash
# Edit .env
BACKEND_PORT=9000
FRONTEND_PORT=5174

docker-compose up -d
# Access at http://localhost:5174 (frontend) and http://localhost:9000 (backend)
```

### Using Docker Volume Instead of Host Mount

If you prefer Docker to manage storage (e.g., for cloud deployments):

Edit `docker-compose.yml`:
```yaml
services:
  conduit:
    volumes:
      # Replace host mount with named volume
      - conduit-data:/data

volumes:
  conduit-data:
    driver: local
```

Then run:
```bash
docker-compose up -d
# Data stored in Docker volume (use 'docker volume inspect conduit-data' to see location)
```

### Production Setup

For production deployments:

1. **Set AUTH_ENABLED=true** in `.env`
2. **Generate a strong JWT_SECRET:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   # Copy output to JWT_SECRET in .env
   ```
3. **Use Docker volume or network storage** for `DATA_DIR_HOST`
4. **Enable HTTPS** (use reverse proxy like nginx or Traefik)
5. **Set CORS_ALLOWED_ORIGINS** to your domain, not localhost

---

## Troubleshooting

### Port Already in Use

```bash
# Find what's using the port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Change in .env
BACKEND_PORT=9000
FRONTEND_PORT=5174
```

### Data Not Persisting

```bash
# Verify mount point in docker-compose
docker inspect conduit | grep -A 10 "Mounts"

# Check data directory exists and is writable
ls -la ./conduit-data/
chmod 755 ./conduit-data/
```

### Container Won't Start

```bash
# Check logs
docker-compose logs conduit

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### Scripts Not Running

```bash
# Verify Python is available in container
docker-compose exec conduit python --version

# Check data/scripts directory
docker-compose exec conduit ls -la /data/scripts/
```

---

## Architecture

```
┌──────────────────────────────────────────┐
│      Docker Container (Conduit)          │
├──────────────────────────────────────────┤
│                                          │
│  Backend (FastAPI + uvicorn)             │
│    ├─ API routes                         │
│    ├─ Script runner (subprocesses)       │
│    ├─ Scheduler (cron jobs)              │
│    └─ Metrics collector                  │
│                                          │
│  Frontend (React + Vite)                 │
│    ├─ Dashboard                          │
│    ├─ Script editor                      │
│    └─ Execution logs                     │
│                                          │
│  Database (SQLite)                       │
│    └─ Persisted to /data/conduit.db      │
│                                          │
│  Script Files                            │
│    └─ Persisted to /data/scripts/        │
│                                          │
└──────────────────────────────────────────┘
           │
           ├─► Volume Mount: /data
           │   └─ Host: ./conduit-data/ (or custom path)
           │
           ├─► Port 8000 (backend)
           └─► Port 5173 (frontend)
```

---

## What's Included

- **Python 3.11** runtime with all dependencies
- **Node.js 20** for frontend build tooling
- **FastAPI** backend with async support
- **React** frontend with TypeScript
- **SQLite** database for metadata
- **APScheduler** for cron jobs
- **Uvicorn** ASGI server

All in a single, self-contained ~1.5GB image.

---

## Next Steps

1. **Create a script** in the UI to test execution
2. **Run the script** and verify output in the execution log
3. **Stop the container** and verify data persists on disk
4. **Restart** the container and confirm scripts are still there

For production use, refer to the **Production Setup** section above.

---

## Questions or Issues?

See `README.md` for more information about Conduit itself.
