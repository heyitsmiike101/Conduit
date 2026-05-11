"""
Health check endpoint.

GET /api/v1/health  — simple liveness probe.
Returns basic platform status: DB reachable, runner state, queue depth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.services.runner_service import runner_service

router = APIRouter()


@router.get("/health", summary="Platform health check")
def health_check(db: Session = Depends(get_db)) -> dict:
    """
    Returns 200 if the platform is up.

    Checks:
      - DB: execute a trivial query (confirms connection)
      - Runner: active execution count and queue depth

    Also exposes current (read-only) platform settings so the UI can display
    them without a separate config endpoint.
    """
    # Trivial DB probe — if the engine is broken this will raise and FastAPI
    # will return a 500, which is the correct signal for an unhealthy service.
    db.execute(__import__("sqlalchemy").text("SELECT 1"))

    import psutil as _psutil
    from app.core.config import settings as _settings
    _disk  = _psutil.disk_usage(str(_settings.data_dir))
    _mem   = _psutil.virtual_memory()
    _cpu_count = _psutil.cpu_count(logical=True)

    return {
        "status": "ok",
        "active_executions": len(runner_service.get_active_executions()),
        "queue_depth": runner_service.get_queue_depth(),
        # Disk
        "disk_free_gb":  round(_disk.free  / (1024 ** 3), 2),
        "disk_used_gb":  round(_disk.used  / (1024 ** 3), 2),
        "disk_total_gb": round(_disk.total / (1024 ** 3), 2),
        "disk_percent":  round(_disk.percent, 1),
        # Memory
        "memory_used_gb":  round(_mem.used  / (1024 ** 3), 2),
        "memory_total_gb": round(_mem.total / (1024 ** 3), 2),
        "memory_percent":  round(_mem.percent, 1),
        # CPU
        "cpu_count": _cpu_count,
        "settings": {
            "max_concurrent_scripts": settings.max_concurrent_scripts,
            "metrics_interval_seconds": settings.metrics_interval_seconds,
            "warn_threshold": settings.warn_threshold,
            "critical_threshold": settings.critical_threshold,
            "cors_allowed_origins": settings.cors_allowed_origins,
            "log_level": settings.log_level,
            "database_url": settings.database_url,
        },
    }
