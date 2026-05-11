"""
Executions API — trigger runs and query execution history.

Routes:
  POST   /executions                  — trigger a script run (manual)
  GET    /executions                  — list executions (optional ?script_id= filter)
  GET    /executions/{id}             — get one execution
  GET    /executions/{id}/logs        — get execution log lines
  POST   /executions/{id}/cancel      — cancel a running or queued execution
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Execution, ExecutionLog
from app.schemas.executions import ExecutionResponse, ExecutionTrigger, ExecutionLogResponse
from app.services.runner_service import runner_service, ScriptAlreadyRunningError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/executions", tags=["executions"])


@router.post("", response_model=ExecutionResponse, status_code=202)
async def trigger_execution(
    body: ExecutionTrigger,
    db: Session = Depends(get_db),
) -> Execution:
    """
    Trigger a script run.

    Returns 202 Accepted with the new Execution record.
    The run is started immediately (or queued if the concurrency limit is reached).
    """
    from app.db.models import Script
    script = db.query(Script).filter_by(id=body.script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{body.script_id}' not found")
    if not script.enabled:
        raise HTTPException(status_code=422, detail=f"Script '{body.script_id}' is disabled")

    try:
        execution_id = await runner_service.run_script(body.script_id, db)
    except ScriptAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    execution = db.query(Execution).filter_by(id=execution_id).first()
    return execution


@router.get("", response_model=list[ExecutionResponse])
def list_executions(
    script_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    started_after: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[Execution]:
    """
    Return execution history, newest first.

    Optional ?script_id= to filter to one script.
    Optional ?status=  to filter by status (queued|running|success|failed|timeout|interrupted).
    Optional ?started_after=ISO8601 to filter executions started after this timestamp (e.g., 2026-05-11T00:00:00Z).
    Optional ?limit=   to cap results (default 50, 0 = no limit).
    """
    query = db.query(Execution)
    if script_id is not None:
        query = query.filter(Execution.script_id == script_id)
    if status is not None:
        query = query.filter(Execution.status == status)
    if started_after is not None:
        try:
            cutoff = datetime.fromisoformat(started_after.replace('Z', '+00:00'))
            query = query.filter(Execution.started_at >= cutoff)
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid started_after format (use ISO8601 with Z)")
    query = query.order_by(Execution.started_at.desc())
    if limit > 0:
        query = query.limit(limit)
    return query.all()


@router.get("/{execution_id}", response_model=ExecutionResponse)
def get_execution(execution_id: str, db: Session = Depends(get_db)) -> Execution:
    """Return a single execution by ID."""
    execution = db.query(Execution).filter_by(id=execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
    return execution


@router.get("/{execution_id}/logs", response_model=list[ExecutionLogResponse])
def get_execution_logs(
    execution_id: str,
    stream: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[ExecutionLog]:
    """
    Return log lines for an execution, ordered by timestamp.

    Optional ?stream=stdout|stderr|api to filter by stream.
    """
    execution = db.query(Execution).filter_by(id=execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")

    query = db.query(ExecutionLog).filter(ExecutionLog.execution_id == execution_id)
    if stream is not None:
        query = query.filter(ExecutionLog.stream == stream)
    return query.order_by(ExecutionLog.timestamp, ExecutionLog.id).all()


@router.post("/{execution_id}/cancel", status_code=204)
async def cancel_execution(
    execution_id: str,
    db: Session = Depends(get_db),
) -> None:
    """
    Cancel a running or queued execution.

    Sends SIGTERM to the subprocess if running.
    Returns 204 even if the execution was already finished (idempotent).
    """
    execution = db.query(Execution).filter_by(id=execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")

    await runner_service.cancel_script(execution_id, db)
