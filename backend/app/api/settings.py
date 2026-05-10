"""
Settings API — read and update runtime platform configuration.

Routes:
  GET   /settings  — return current mutable settings
  PATCH /settings  — update one or more settings values (takes effect immediately,
                     persisted to data/settings_override.json for restart survival)

Immutable settings (database_url, data_dir, secret_key_path) are not exposed
here — they can only be changed via environment variables before startup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Path where runtime overrides are persisted
_OVERRIDE_FILE = settings.data_dir / "settings_override.json"

# Fields that can be changed at runtime
MUTABLE_FIELDS = {
    "max_concurrent_scripts",
    "metrics_interval_seconds",
    "warn_threshold",
    "critical_threshold",
    "cors_allowed_origins",
    "log_level",
}


class SettingsPatch(BaseModel):
    max_concurrent_scripts: Optional[int] = Field(None, ge=1)
    metrics_interval_seconds: Optional[int] = Field(None, ge=5)
    warn_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    critical_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    cors_allowed_origins: Optional[List[str]] = None
    log_level: Optional[str] = Field(None, pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")


def _load_overrides() -> dict:
    """Load persisted overrides from disk (empty dict if file absent)."""
    if _OVERRIDE_FILE.exists():
        try:
            return json.loads(_OVERRIDE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_overrides(data: dict) -> None:
    """Write override dict to disk."""
    _OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDE_FILE.write_text(json.dumps(data, indent=2))


def apply_overrides_from_disk() -> None:
    """
    Called at startup to apply any persisted overrides to the in-memory Settings object.
    """
    overrides = _load_overrides()
    for key, value in overrides.items():
        if key in MUTABLE_FIELDS and hasattr(settings, key):
            setattr(settings, key, value)
            logger.info("Settings override applied: %s = %r", key, value)


def _settings_dict() -> dict:
    return {
        "max_concurrent_scripts": settings.max_concurrent_scripts,
        "metrics_interval_seconds": settings.metrics_interval_seconds,
        "warn_threshold": settings.warn_threshold,
        "critical_threshold": settings.critical_threshold,
        "cors_allowed_origins": settings.cors_allowed_origins,
        "log_level": settings.log_level,
        "database_url": settings.database_url,
    }


@router.get("")
def get_settings() -> dict:
    """Return current platform settings (mutable + informational read-only fields)."""
    return _settings_dict()


@router.patch("")
def patch_settings(body: SettingsPatch) -> dict:
    """
    Update one or more mutable settings values.

    Changes take effect immediately in the running process and are written to
    data/settings_override.json so they survive a restart.
    """
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    # Validate critical > warn
    new_warn = updates.get("warn_threshold", settings.warn_threshold)
    new_crit = updates.get("critical_threshold", settings.critical_threshold)
    if new_crit <= new_warn:
        raise HTTPException(
            status_code=422,
            detail="critical_threshold must be greater than warn_threshold",
        )

    # Apply to in-memory settings object
    for key, value in updates.items():
        setattr(settings, key, value)
        logger.info("Setting updated: %s = %r", key, value)

    # Persist all current overrides (merge with existing)
    persisted = _load_overrides()
    persisted.update(updates)
    _save_overrides(persisted)

    return _settings_dict()
