"""
Scheduler service — APScheduler wrapper.

Wraps APScheduler's BackgroundScheduler with a clean public interface so the
underlying engine can be swapped (e.g. to Celery) without touching callers.

Jobs are persisted to the same SQLite database via SQLAlchemyJobStore, so
scheduled jobs survive app restarts automatically.

Public interface:
  add_job(script_id, cron_expression) -> job_id
  remove_job(job_id)
  pause_job(job_id)
  resume_job(job_id)
  list_jobs() -> list[dict]
  start()
  shutdown()
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor

from app.core.config import settings

logger = logging.getLogger(__name__)

# The event loop captured at startup — used to bridge APScheduler's thread
# callbacks into the running asyncio event loop.
_loop: Optional[asyncio.AbstractEventLoop] = None


def _trigger_script(script_id: str, cron_expression: str) -> None:
    """
    APScheduler callback — runs in a background thread pool.

    1. Updates the cron_jobs.last_run timestamp synchronously (fast DB write).
    2. Submits the async run_script coroutine to the main asyncio event loop
       so it executes in the correct async context.
    """
    from app.services.runner_service import runner_service
    from app.db.session import SessionLocal
    from app.db.models import CronJob

    fired_at = datetime.utcnow()

    # Update cron_jobs.last_run for this firing (best-effort, do not block run)
    db_sync = SessionLocal()
    try:
        cron_job = (
            db_sync.query(CronJob)
            .filter(
                CronJob.script_id == script_id,
                CronJob.cron_expression == cron_expression,
            )
            .first()
        )
        if cron_job:
            cron_job.last_run = fired_at
            # Refresh next_run from the live scheduler
            try:
                aps_job = scheduler_service._scheduler.get_job(cron_job.id)
                if aps_job and aps_job.next_run_time:
                    # Strip timezone for storage (DB column is naive UTC by convention)
                    next_run = aps_job.next_run_time
                    if next_run.tzinfo is not None:
                        next_run = next_run.replace(tzinfo=None)
                    cron_job.next_run = next_run
            except Exception:  # pragma: no cover — best-effort
                pass
            db_sync.commit()
    except Exception as exc:
        logger.warning("Failed to update last_run for script %s: %s", script_id, exc)
    finally:
        db_sync.close()

    async def _run() -> None:
        from app.services.runner_service import ScriptAlreadyRunningError
        db = SessionLocal()
        try:
            await runner_service.run_script(script_id, db)
        except ScriptAlreadyRunningError as exc:
            # Log + create a notification so the user sees why the cron skipped a run.
            logger.warning(
                "Cron-triggered run for script %s skipped: %s", script_id, exc,
            )
            try:
                from app.services.notifications_service import create_notification
                from app.db.models import NotificationLevel
                create_notification(
                    db=db,
                    level=NotificationLevel.WARN,
                    category="cron_skipped",
                    message=(
                        f"Scheduled run skipped — previous run is still "
                        f"{exc.status} (execution {exc.existing_execution_id})."
                    ),
                    metadata={
                        "script_id": script_id,
                        "existing_execution_id": exc.existing_execution_id,
                    },
                )
            except Exception:  # pragma: no cover — best-effort
                pass
        except Exception as exc:
            logger.error("Scheduled run failed for script %s: %s", script_id, exc)
        finally:
            db.close()

    if _loop and _loop.is_running():
        asyncio.run_coroutine_threadsafe(_run(), _loop)
    else:
        logger.error(
            "Cannot trigger script %s — no running event loop found", script_id
        )


class SchedulerService:
    """
    Thin wrapper around APScheduler. All Conduit code should use this class
    rather than APScheduler directly.
    """

    def __init__(self) -> None:
        jobstore = SQLAlchemyJobStore(url=settings.database_url)
        executor = ThreadPoolExecutor(max_workers=10)

        self._scheduler = BackgroundScheduler(
            jobstores={"default": jobstore},
            executors={"default": executor},
            job_defaults={"coalesce": True, "max_instances": 1},
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler and capture the current event loop."""
        global _loop
        try:
            _loop = asyncio.get_event_loop()
        except RuntimeError:
            _loop = None

        self._scheduler.start()
        logger.info("Scheduler started — %d persisted jobs loaded", len(self._scheduler.get_jobs()))

    def shutdown(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler shut down")

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def add_job(self, script_id: str, cron_expression: str, job_id: Optional[str] = None) -> str:
        """
        Schedule a script on a cron expression.

        Args:
            script_id: The script to run when the trigger fires.
            cron_expression: Standard 5-field cron string (already validated by schema).
            job_id: Optional explicit job ID. Defaults to a generated ID.

        Returns:
            The APScheduler job ID (use this to pause/remove the job later).
        """
        trigger = CronTrigger.from_crontab(cron_expression)

        job = self._scheduler.add_job(
            func=_trigger_script,
            trigger=trigger,
            id=job_id,
            kwargs={"script_id": script_id, "cron_expression": cron_expression},
            replace_existing=True,
        )
        logger.info(
            "Scheduled job %s for script %s — expression: %s  next: %s",
            job.id, script_id, cron_expression, job.next_run_time,
        )
        return job.id

    def remove_job(self, job_id: str) -> None:
        """
        Remove a scheduled job.

        Raises:
            ValueError: If the job does not exist.
        """
        try:
            self._scheduler.remove_job(job_id)
            logger.info("Removed scheduled job %s", job_id)
        except Exception as exc:
            raise ValueError(f"Job '{job_id}' not found: {exc}") from exc

    def pause_job(self, job_id: str) -> None:
        """Pause a job (it will not fire until resumed)."""
        self._scheduler.pause_job(job_id)
        logger.info("Paused job %s", job_id)

    def resume_job(self, job_id: str) -> None:
        """Resume a paused job."""
        self._scheduler.resume_job(job_id)
        logger.info("Resumed job %s", job_id)

    def list_jobs(self) -> List[Dict]:
        """
        Return info about all scheduled jobs.

        Returns:
            List of dicts with keys: job_id, script_id, cron_expression, next_run, paused.
        """
        jobs = []
        for job in self._scheduler.get_jobs():
            kwargs = job.kwargs or {}
            next_run = job.next_run_time  # None when paused
            jobs.append({
                "job_id": job.id,
                "script_id": kwargs.get("script_id"),
                "cron_expression": kwargs.get("cron_expression"),
                "next_run": next_run,
                "paused": next_run is None,
            })
        return jobs


# Exported singleton
scheduler_service = SchedulerService()
