"""
Pydantic schemas for CronJob resources.

CronJobCreate validates cron expressions at the schema level using croniter
so invalid expressions are rejected with a 422 before touching the database.
CronJobResponse includes a human-readable description and upcoming run times.
"""

from datetime import datetime
from typing import List, Optional

from croniter import croniter
from cron_descriptor import get_description, ExpressionDescriptor
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CronJobCreate(BaseModel):
    script_id: str
    name: Optional[str] = Field(None, max_length=255, description="Friendly name for this schedule")
    description: Optional[str] = Field(None, description="What does this schedule do?")
    cron_expression: str = Field(..., description="Standard 5-field cron expression (min hr dom mon dow)")
    enabled: bool = True

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, value: str) -> str:
        if not croniter.is_valid(value):
            raise ValueError(
                f"Invalid cron expression: '{value}'. "
                "Expected 5-field format: minute hour day-of-month month day-of-week. "
                "Example: '0 9 * * 1-5' (weekdays at 9am)."
            )
        return value


class CronJobUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    cron_expression: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not croniter.is_valid(value):
            raise ValueError(f"Invalid cron expression: '{value}'")
        return value


class CronJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    script_id: str
    name: Optional[str]
    description: Optional[str]
    cron_expression: str
    enabled: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    human_readable: str = ""

    @model_validator(mode="after")
    def compute_human_readable(self) -> "CronJobResponse":
        """Generate a plain-English description of the cron schedule."""
        try:
            self.human_readable = get_description(self.cron_expression)
        except Exception:
            self.human_readable = self.cron_expression
        return self


# ---------------------------------------------------------------------------
# Validate endpoint schemas
# ---------------------------------------------------------------------------


class CronValidateRequest(BaseModel):
    cron_expression: str


class CronValidateResponse(BaseModel):
    valid: bool
    human_readable: str = ""
    next_runs: List[datetime] = Field(default_factory=list)
