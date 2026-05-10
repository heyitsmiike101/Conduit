"""
Notifications service.

Notifications are persistent platform alerts (system health, missing files, etc.).
They are never auto-resolved — only manual dismissal via the UI clears them.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import Notification, NotificationLevel

logger = logging.getLogger(__name__)


def create_notification(
    level: NotificationLevel,
    category: str,
    message: str,
    db: Session,
    metadata: Optional[Dict] = None,
) -> Notification:
    """
    Create a new platform notification.

    Args:
        level: Severity — info, warn, or critical.
        category: Machine-readable category string (e.g. "system_health", "missing_script_file").
        message: Human-readable description shown in the UI.
        metadata: Optional dict of extra context (stored as JSON).
        db: SQLAlchemy session (required — no default, callers must always pass one).
        metadata: Optional dict of extra context (stored as JSON).
    """
    notification = Notification(
        level=level,
        category=category,
        message=message,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    logger.info(
        "Notification created [%s/%s]: %s", level.value, category, message
    )
    return notification


def list_notifications(
    db: Session,
    dismissed: bool = False,
) -> List[Notification]:
    """
    Return notifications.

    Args:
        dismissed: If False (default), return only undismissed notifications.
                   If True, return all notifications including dismissed ones.
    """
    query = db.query(Notification)
    if not dismissed:
        query = query.filter(Notification.dismissed_at.is_(None))
    return query.order_by(Notification.created_at.desc()).all()


def dismiss_notification(notification_id: str, db: Session) -> Notification:
    """
    Mark a notification as dismissed. Sets dismissed_at to now.

    Raises:
        ValueError: If the notification does not exist.
    """
    notification = db.query(Notification).filter_by(id=notification_id).first()
    if not notification:
        raise ValueError(f"Notification '{notification_id}' not found")

    notification.dismissed_at = datetime.utcnow()
    db.commit()
    db.refresh(notification)
    return notification


def get_unread_count(db: Session) -> int:
    """Return the number of undismissed notifications."""
    return db.query(Notification).filter(Notification.dismissed_at.is_(None)).count()


def dismiss_all_notifications(db: Session) -> int:
    """
    Mark every undismissed notification as dismissed.

    Returns the number of notifications that were dismissed.
    """
    now = datetime.utcnow()
    count = (
        db.query(Notification)
        .filter(Notification.dismissed_at.is_(None))
        .update({"dismissed_at": now}, synchronize_session=False)
    )
    db.commit()
    logger.info("Dismissed %d notifications (bulk)", count)
    return count
