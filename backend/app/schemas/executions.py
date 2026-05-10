"""Pydantic schemas for Execution and ExecutionLog resources."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import ExecutionStatus, LogStream


class ExecutionTrigger(BaseModel):
    """Request body for POST /executions — manually trigger a script run."""

    script_id: str = Field(..., description="ID of the script to run")


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    script_id: str
    started_at: datetime
    finished_at: Optional[datetime]
    return_code: Optional[int]
    status: ExecutionStatus
    duration_seconds: Optional[float] = None

    @model_validator(mode="after")
    def compute_duration(self) -> "ExecutionResponse":
        """Derive duration from start/finish timestamps when both are present."""
        if self.started_at and self.finished_at:
            self.duration_seconds = round(
                (self.finished_at - self.started_at).total_seconds(), 3
            )
        return self


class ExecutionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: str
    stream: LogStream
    content: str
    timestamp: datetime
