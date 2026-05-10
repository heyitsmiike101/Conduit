"""
Notifications API — read and dismiss platform alerts.

Routes:
  GET    /notifications               — list notifications (undismissed by default)
  GET    /notifications/count         — count of unread notifications
  POST   /notifications/{id}/dismiss  — mark a notification dismissed
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.notifications import NotificationResponse
from app.services.notifications_service import (
    dismiss_all_notifications,
    dismiss_notification,
    get_unread_count,
    list_notifications,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def list_notifications_route(
    include_dismissed: bool = False,
    db: Session = Depends(get_db),
) -> list:
    """
    Return notifications.

    By default returns only undismissed ones.
    Pass ?include_dismissed=true to include dismissed notifications.
    """
    return list_notifications(db=db, dismissed=include_dismissed)


@router.get("/count")
def get_unread_count_route(db: Session = Depends(get_db)) -> dict:
    """Return the count of undismissed notifications."""
    return {"count": get_unread_count(db)}


@router.post("/dismiss-all")
def dismiss_all_route(db: Session = Depends(get_db)) -> dict:
    """Dismiss all currently undismissed notifications."""
    count = dismiss_all_notifications(db)
    return {"dismissed": count}


@router.post("/{notification_id}/dismiss", response_model=NotificationResponse)
def dismiss_notification_route(
    notification_id: str,
    db: Session = Depends(get_db),
) -> object:
    """Mark a notification as dismissed."""
    try:
        return dismiss_notification(notification_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
