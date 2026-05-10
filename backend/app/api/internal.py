"""
Internal API — endpoints called by conduit-helper from running scripts.

These routes are NOT part of the public UI API. Scripts call them via the
conduit-helper library using the execution ID injected at launch time.

Authentication:
  All internal routes require the X-Execution-ID header. The value is
  validated against the executions table — only active execution IDs are
  accepted (status RUNNING). Missing or unknown IDs → 401.

Routes:
  POST /internal/log-api-call    — log an outbound HTTP call made by a script
  POST /internal/trigger-script  — trigger another script from within a script
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Execution, ExecutionLog, ExecutionStatus, LogStream, Script

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


# ---------------------------------------------------------------------------
# Header dependency — resolves execution_id from X-Execution-ID
# ---------------------------------------------------------------------------


def _require_execution(
    x_execution_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> str:
    """
    Validate the X-Execution-ID header and return the execution_id.

    Raises 401 if the header is missing or does not match a RUNNING execution.
    """
    if not x_execution_id:
        raise HTTPException(
            status_code=401,
            detail="X-Execution-ID header is required for internal endpoints",
        )

    execution = db.query(Execution).filter_by(id=x_execution_id).first()
    if not execution or execution.status != ExecutionStatus.RUNNING:
        raise HTTPException(
            status_code=401,
            detail=f"Execution '{x_execution_id}' is not active",
        )

    return x_execution_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LogApiCallRequest(BaseModel):
    """Body for the log-api-call endpoint."""

    method: str                          # HTTP method, e.g. "GET"
    url: str                             # Full URL that was called
    status_code: int                     # Response status code
    duration_ms: float                   # Round-trip time in milliseconds
    metadata: Optional[Dict[str, Any]] = None  # Extra context (headers, error, etc.)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/log-api-call", status_code=204)
def log_api_call(
    body: LogApiCallRequest,
    execution_id: str = Depends(_require_execution),
    db: Session = Depends(get_db),
) -> None:
    """
    Record an outbound HTTP call made by a running script.

    Written as an ExecutionLog row with stream="api" so it appears in
    the execution's log alongside stdout/stderr.
    """
    entry = {
        "method": body.method,
        "url": body.url,
        "status_code": body.status_code,
        "duration_ms": body.duration_ms,
    }
    if body.metadata:
        entry["metadata"] = body.metadata

    db.add(ExecutionLog(
        execution_id=execution_id,
        stream=LogStream.API,
        content=json.dumps(entry),
    ))
    db.commit()

    logger.debug(
        "API call logged for execution %s: %s %s → %d (%.1fms)",
        execution_id, body.method, body.url, body.status_code, body.duration_ms,
    )


class TriggerScriptRequest(BaseModel):
    """Body for the trigger-script endpoint."""
    script_id: str


@router.post("/trigger-script", status_code=202)
async def trigger_script(
    body: TriggerScriptRequest,
    execution_id: str = Depends(_require_execution),
    db: Session = Depends(get_db),
) -> dict:
    """
    Trigger another script from within a running script.

    The new execution is queued independently — the caller does not wait
    for it to complete. Returns the new execution's ID.

    Returns 409 if the target script is already running or queued.
    """
    from app.services.runner_service import runner_service, ScriptAlreadyRunningError

    script = db.query(Script).filter_by(id=body.script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{body.script_id}' not found")
    if not script.enabled:
        raise HTTPException(status_code=409, detail=f"Script '{body.script_id}' is disabled")

    try:
        new_exec_id = await runner_service.run_script(body.script_id, db)
    except ScriptAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    new_exec = db.query(Execution).filter_by(id=new_exec_id).first()
    logger.info(
        "Script %s triggered by execution %s → new execution %s",
        body.script_id, execution_id, new_exec_id,
    )
    return {"execution_id": new_exec.id, "status": new_exec.status.value}
