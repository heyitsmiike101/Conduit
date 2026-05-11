"""
Audit Log API — read-only access to the platform audit trail.

Routes:
  GET /audit-logs                   — list audit log entries (requires auth when enabled)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_user
from app.db.models import AuditLog
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    username: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    resource_name: Optional[str]
    ip_address: Optional[str]
    metadata: Optional[dict[str, Any]]
    created_at: str

    @classmethod
    def from_orm(cls, row: AuditLog) -> "AuditLogResponse":
        return cls(
            id=row.id,
            user_id=row.user_id,
            username=row.username,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            resource_name=row.resource_name,
            ip_address=row.ip_address,
            metadata=json.loads(row.metadata_json) if row.metadata_json else None,
            created_at=row.created_at.isoformat(),
        )


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action string (exact or prefix)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum entries to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    _user=Depends(require_user),
    db: Session = Depends(get_db),
):
    """
    Return audit log entries, newest first.

    Supports filtering by action, resource type, resource ID, and user.
    """
    q = db.query(AuditLog)

    if action:
        # Prefix match: "script" matches "script.create", "script.delete", etc.
        q = q.filter(AuditLog.action.like(f"{action}%"))
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        q = q.filter(AuditLog.resource_id == resource_id)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)

    rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return [AuditLogResponse.from_orm(r) for r in rows]
