"""Pydantic schemas for Notification resources."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.db.models import NotificationLevel


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    level: NotificationLevel
    category: str
    message: str
    metadata_json: Optional[str]
    created_at: datetime
    dismissed_at: Optional[datetime]
    is_dismissed: bool = False

    @model_validator(mode="after")
    def compute_is_dismissed(self) -> "NotificationResponse":
        self.is_dismissed = self.dismissed_at is not None
        return self


class NotificationCountResponse(BaseModel):
    unread: int
