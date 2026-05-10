"""
Cron Jobs API — schedule management for scripts.

Routes:
  GET    /cron-jobs                   — list all scheduled jobs
  POST   /cron-jobs                   — create a scheduled job
  GET    /cron-jobs/{id}              — get one cron job
  PATCH  /cron-jobs/{id}              — update expression or enabled state
  DELETE /cron-jobs/{id}              — remove the scheduled job
  POST   /cron-jobs/{id}/pause        — pause a job
  POST   /cron-jobs/{id}/resume       — resume a paused job
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import CronJob, Script
from app.schemas.cron_jobs import CronJobCreate, CronJobResponse, CronJobUpdate
from app.services.scheduler_service import scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron-jobs", tags=["cron-jobs"])


def _refresh_next_run(jobs: List[CronJob], db: Session) -> List[CronJob]:
    """Sync next_run from APScheduler (which knows the real next fire time)."""
    live = {j["job_id"]: j for j in scheduler_service.list_jobs()}
    dirty = False
    for cj in jobs:
        if cj.id in live:
            next_run = live[cj.id]["next_run"]
            if next_run is not None and next_run.tzinfo is not None:
                next_run = next_run.replace(tzinfo=None)
            if cj.next_run != next_run:
                cj.next_run = next_run
                dirty = True
    if dirty:
        db.commit()
    return jobs


@router.get("", response_model=list[CronJobResponse])
def list_cron_jobs(
    script_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[CronJob]:
    """List all cron jobs. Optional ?script_id= filter."""
    query = db.query(CronJob)
    if script_id is not None:
        query = query.filter(CronJob.script_id == script_id)
    jobs = query.order_by(CronJob.script_id).all()
    return _refresh_next_run(jobs, db)


@router.post("", response_model=CronJobResponse, status_code=201)
def create_cron_job(body: CronJobCreate, db: Session = Depends(get_db)) -> CronJob:
    """
    Create and immediately schedule a cron job.

    The APScheduler job ID is stored in cron_jobs.id so it can be
    paused/removed later.
    """
    script = db.query(Script).filter_by(id=body.script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{body.script_id}' not found")

    cron_job = CronJob(
        script_id=body.script_id,
        name=body.name,
        description=body.description,
        cron_expression=body.cron_expression,
        enabled=True,
    )
    db.add(cron_job)
    # Commit BEFORE calling add_job. APScheduler's SQLAlchemyJobStore writes to the
    # same SQLite DB file in a separate connection. SQLite only allows one writer at a
    # time — if we hold an open write transaction here, the jobstore write will block
    # indefinitely. Committing releases our lock first.
    db.commit()
    db.refresh(cron_job)

    try:
        scheduler_service.add_job(
            script_id=body.script_id,
            cron_expression=body.cron_expression,
            job_id=cron_job.id,
        )
    except Exception as exc:
        # Scheduler failed — remove the DB row we just committed
        db.delete(cron_job)
        db.commit()
        raise HTTPException(status_code=422, detail=f"Failed to schedule job: {exc}") from exc

    # Populate next_run from the scheduler (available now that the job exists)
    jobs = {j["job_id"]: j for j in scheduler_service.list_jobs()}
    if cron_job.id in jobs:
        cron_job.next_run = jobs[cron_job.id]["next_run"]
        db.commit()
        db.refresh(cron_job)

    return cron_job


@router.get("/{cron_job_id}", response_model=CronJobResponse)
def get_cron_job(cron_job_id: str, db: Session = Depends(get_db)) -> CronJob:
    """Return a single cron job by ID."""
    cron_job = db.query(CronJob).filter_by(id=cron_job_id).first()
    if not cron_job:
        raise HTTPException(status_code=404, detail=f"Cron job '{cron_job_id}' not found")
    _refresh_next_run([cron_job], db)
    return cron_job


@router.patch("/{cron_job_id}", response_model=CronJobResponse)
def update_cron_job(
    cron_job_id: str,
    body: CronJobUpdate,
    db: Session = Depends(get_db),
) -> CronJob:
    """
    Update a cron job.

    If cron_expression changes, the APScheduler job is re-registered.
    If enabled changes to False, the job is paused; True resumes it.
    """
    cron_job = db.query(CronJob).filter_by(id=cron_job_id).first()
    if not cron_job:
        raise HTTPException(status_code=404, detail=f"Cron job '{cron_job_id}' not found")

    update_data = body.model_dump(exclude_unset=True)

    if "cron_expression" in update_data:
        new_expression = update_data["cron_expression"]
        try:
            scheduler_service.add_job(
                script_id=cron_job.script_id,
                cron_expression=new_expression,
                job_id=cron_job.id,  # replace_existing=True in scheduler
            )
            cron_job.cron_expression = new_expression
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid cron expression: {exc}") from exc

    if "enabled" in update_data:
        if update_data["enabled"]:
            scheduler_service.resume_job(cron_job.id)
        else:
            scheduler_service.pause_job(cron_job.id)
        cron_job.enabled = update_data["enabled"]

    db.commit()
    db.refresh(cron_job)
    return cron_job


@router.delete("/{cron_job_id}", status_code=204)
def delete_cron_job(cron_job_id: str, db: Session = Depends(get_db)) -> None:
    """Remove a cron job from both the scheduler and the database."""
    cron_job = db.query(CronJob).filter_by(id=cron_job_id).first()
    if not cron_job:
        raise HTTPException(status_code=404, detail=f"Cron job '{cron_job_id}' not found")

    try:
        scheduler_service.remove_job(cron_job.id)
    except ValueError:
        # Job already gone from scheduler — proceed with DB delete anyway
        logger.warning("APScheduler job %s already removed; cleaning up DB row", cron_job_id)

    db.delete(cron_job)
    db.commit()


@router.post("/{cron_job_id}/pause", response_model=CronJobResponse)
def pause_cron_job(cron_job_id: str, db: Session = Depends(get_db)) -> CronJob:
    """Pause a scheduled job."""
    cron_job = db.query(CronJob).filter_by(id=cron_job_id).first()
    if not cron_job:
        raise HTTPException(status_code=404, detail=f"Cron job '{cron_job_id}' not found")

    scheduler_service.pause_job(cron_job.id)
    cron_job.enabled = False
    db.commit()
    db.refresh(cron_job)
    return cron_job


@router.post("/{cron_job_id}/resume", response_model=CronJobResponse)
def resume_cron_job(cron_job_id: str, db: Session = Depends(get_db)) -> CronJob:
    """Resume a paused scheduled job."""
    cron_job = db.query(CronJob).filter_by(id=cron_job_id).first()
    if not cron_job:
        raise HTTPException(status_code=404, detail=f"Cron job '{cron_job_id}' not found")

    scheduler_service.resume_job(cron_job.id)
    cron_job.enabled = True
    db.commit()
    db.refresh(cron_job)
    return cron_job
