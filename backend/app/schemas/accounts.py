"""Pydantic schemas for Account resources."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Unique account name")


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime
