"""
Audit logging service — append-only trail of sensitive platform operations.

Every call writes one row to audit_logs. The table is never modified after
insert — it is a compliance record of what happened.

Usage (in any route handler):
    from app.services.audit_service import audit

    audit(
        db=db,
        action="script.delete",
        resource_type="script",
        resource_id=script.id,
        resource_name=script.name,
        user=current_user,   # may be None when auth is off
        request=request,     # FastAPI Request, used to extract IP
    )

Standard action strings (extend as needed):
    auth.login          auth.logout         auth.setup
    auth.password_change
    script.create       script.delete       script.run
    script.content_save script.revert
    variable.create     variable.delete     variable.update
    variable.reveal     (secret viewed in plaintext)
    table.create        table.delete
    cron_job.create     cron_job.delete
    cron_job.pause      cron_job.resume
    settings.update
    account.create      account.delete
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.db.models import AuditLog, User

logger = logging.getLogger(__name__)


def audit(
    db: Session,
    action: str,
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    user: Optional[User] = None,
    request: Optional[Request] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """
    Write one audit log row.

    This function is intentionally fire-and-forget: errors are logged but
    never bubble up to the caller. An audit failure must never break the
    primary operation.

    Args:
        db:            Live SQLAlchemy session. The row is committed immediately.
        action:        Dot-separated action string, e.g. "script.delete".
        resource_type: Category of the affected resource, e.g. "script".
        resource_id:   UUID of the affected resource.
        resource_name: Human-readable name at time of action.
        user:          Authenticated User ORM object (None if auth is off or setup).
        request:       FastAPI Request, used to extract the client IP address.
        metadata:      Any extra key/value pairs to persist with the log entry.
    """
    try:
        ip_address: Optional[str] = None
        if request:
            # X-Forwarded-For is set by reverse proxies; fall back to direct IP
            forwarded = request.headers.get("x-forwarded-for")
            ip_address = forwarded.split(",")[0].strip() if forwarded else str(request.client.host)

        row = AuditLog(
            user_id=user.id if user else None,
            username=user.username if user else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            ip_address=ip_address,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(row)
        db.commit()

        logger.info(
            "AUDIT %s user=%s resource=%s/%s ip=%s",
            action,
            user.username if user else "anonymous",
            resource_type or "-",
            resource_id or "-",
            ip_address or "-",
        )
    except Exception as exc:
        # Never let audit failure break the primary operation
        logger.error("Failed to write audit log for action '%s': %s", action, exc)
