"""
Conduit platform — FastAPI application entrypoint.

Startup sequence (via lifespan):
  1. configure_logging()       — set log format and level from settings
  2. init_db()                 — create all tables (idempotent)
  3. encryption_service.init() — generate/load Fernet key
  4. Sync check                — verify Script.file_path rows exist on disk;
                                  emit WARNING + Notification for any that are missing
  5. runner_service.restore_state() — recover from prior crash/shutdown
  6. scheduler_service.start() — start APScheduler (loads persisted cron jobs)
  7. metrics_service.start_collection_loop() — begin background metric sampling

Shutdown sequence:
  1. scheduler_service.shutdown()
  2. runner_service.shutdown()   — terminates subprocesses, persists queue
  3. metrics_service.stop_collection_loop()
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.logging import configure_logging
from app.middleware.size_limits import request_size_limiter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages startup and shutdown of all platform services.
    The code before `yield` runs at startup; after `yield` runs at shutdown.
    """
    # 1. Logging first so all subsequent messages are properly formatted
    configure_logging()
    logger.info("Conduit platform starting up...")

    # 1b. Apply any persisted settings overrides from data/settings_override.json
    from app.api.settings import apply_overrides_from_disk
    apply_overrides_from_disk()

    # 2. Database — create tables if they don't exist
    from app.db import init_db
    init_db()

    # 3. Encryption — importing the singleton is sufficient; it auto-loads/creates
    #    the Fernet key on first import. We import it here to surface any key
    #    file errors at startup rather than mid-request.
    from app.core.encryption import encryption_service  # noqa: F401 (side-effect import)
    logger.info("Encryption service ready (key loaded from %s)", encryption_service._key_path)

    # 4. Sync check — verify all Script file_path values still exist on disk
    _sync_check_script_files()

    # 5. Runner — recover from prior crash
    from app.services.runner_service import runner_service
    await runner_service.restore_state()

    # 6. Scheduler — start APScheduler with persisted cron jobs
    from app.services.scheduler_service import scheduler_service
    scheduler_service.start()

    # 7. Metrics — begin background sampling
    from app.services.metrics_service import start_collection_loop
    start_collection_loop()

    logger.info("Conduit platform ready")
    yield

    # ---- Shutdown ----
    logger.info("Conduit platform shutting down...")

    from app.services.metrics_service import stop_collection_loop
    stop_collection_loop()

    from app.services.scheduler_service import scheduler_service
    scheduler_service.shutdown()

    from app.services.runner_service import runner_service
    await runner_service.shutdown()

    logger.info("Conduit platform stopped")


def _sync_check_script_files() -> None:
    """
    Verify that every Script row's file_path still exists on disk.

    Scripts whose files are missing get a WARNING log entry and a platform
    Notification (category="missing_script_file"). This typically means a
    file was manually deleted or a data directory was moved.
    """
    from app.db.session import SessionLocal
    from app.db.models import Script, NotificationLevel
    from app.services.notifications_service import create_notification

    db = SessionLocal()
    try:
        scripts = db.query(Script).all()
        missing = [s for s in scripts if not Path(s.file_path).exists()]
        for script in missing:
            logger.warning(
                "Script '%s' (id=%s) file not found on disk: %s",
                script.name, script.id, script.file_path,
            )
            create_notification(
                level=NotificationLevel.WARN,
                category="missing_script_file",
                message=(
                    f"Script '{script.name}' file is missing from disk: {script.file_path}. "
                    "The script cannot be executed until the file is restored."
                ),
                db=db,
                metadata={"script_id": script.id, "file_path": script.file_path},
            )
        if missing:
            logger.warning(
                "Sync check complete — %d script file(s) missing", len(missing)
            )
        else:
            logger.info("Sync check complete — all script files present")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Rate limiter (60 requests/minute per IP)
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["60/minute"],
        storage_uri="memory://",
    )

    app = FastAPI(
        title="Conduit",
        description="Multi-tenant Python automation platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Attach limiter to app state for use in routes
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Request size limiting — prevent disk/memory exhaustion
    app.middleware("http")(request_size_limiter)

    # CORS — browsers block allow_credentials=True when allow_origins=["*"]
    # so we disable credentials when wildcard is used (internal deployments)
    wildcard = "*" in settings.cors_allowed_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=not wildcard,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"] if wildcard else ["Content-Type", "Authorization"],
    )

    # Register all routers
    _register_routers(app)

    # Serve pre-built frontend static files (Docker production mode)
    # Falls back gracefully if frontend/dist doesn't exist (local dev mode)
    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Mount the pre-built Vite frontend as static files if available."""
    # Try Docker path first, then local dev path
    candidates = [
        Path("/app/frontend/dist"),
        Path(__file__).resolve().parents[3] / "frontend" / "dist",
    ]
    for dist in candidates:
        if dist.exists() and (dist / "index.html").exists():
            # Serve assets (js/css/images) from /assets
            app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")
            # Catch-all: serve index.html for all non-API routes (SPA routing)
            @app.get("/{full_path:path}", include_in_schema=False)
            async def spa_fallback(full_path: str):
                return FileResponse(str(dist / "index.html"))
            logger.info("Frontend static files mounted from %s", dist)
            return
    logger.info("No frontend/dist found — running in API-only mode (use 'npm run dev' for UI)")


def _rate_limit_exceeded_handler(request, exc):
    """Handle rate limit exceeded errors gracefully."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Maximum 60 requests per minute per IP address."
        },
    )


def _register_routers(app: FastAPI) -> None:
    """Mount all API routers under /api/v1."""
    from fastapi import Depends
    from app.core.security import require_user

    from app.api.auth import router as auth_router
    from app.api.audit import router as audit_router
    from app.api.health import router as health_router
    from app.api.accounts import router as accounts_router
    from app.api.scripts import router as scripts_router
    from app.api.variables import router as variables_router
    from app.api.executions import router as executions_router
    from app.api.cron_jobs import router as cron_jobs_router
    from app.api.tables import router as tables_router
    from app.api.notifications import router as notifications_router
    from app.api.internal import router as internal_router
    from app.api.metrics import router as metrics_router
    from app.api.settings import router as settings_router

    api_prefix = "/api/v1"

    # Auth routes — always open (login, setup, status don't require a token)
    app.include_router(auth_router, prefix=api_prefix)

    # All other routes respect require_user:
    #   - auth_enabled=False → require_user returns None, routes work normally
    #   - auth_enabled=True  → require_user enforces valid JWT on every request
    protected = {"dependencies": [Depends(require_user)]}

    app.include_router(health_router, prefix=api_prefix)
    app.include_router(accounts_router, prefix=api_prefix, **protected)
    app.include_router(scripts_router, prefix=api_prefix, **protected)
    app.include_router(variables_router, prefix=api_prefix, **protected)
    app.include_router(executions_router, prefix=api_prefix, **protected)
    app.include_router(cron_jobs_router, prefix=api_prefix, **protected)
    app.include_router(tables_router, prefix=api_prefix, **protected)
    app.include_router(notifications_router, prefix=api_prefix, **protected)
    app.include_router(internal_router, prefix=api_prefix)  # Uses its own X-Execution-ID auth
    app.include_router(metrics_router, prefix=api_prefix, **protected)
    app.include_router(settings_router, prefix=api_prefix, **protected)
    app.include_router(audit_router, prefix=api_prefix, **protected)


# Create the application instance
app = create_app()
