"""
Runner service — the core of the Conduit platform.

Manages the full lifecycle of script subprocess executions:
  1. Concurrency enforcement (configurable limit, overflow queued FIFO)
  2. Secure config file injection (via config_injector_service)
  3. Subprocess spawning with stdout/stderr capture
  4. Execution log persistence
  5. Graceful shutdown (marks running as interrupted, persists queue)
  6. State restore on startup (picks up where it left off after restart)

One RunnerService instance exists per process (singleton at module bottom).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Execution, ExecutionLog, ExecutionStatus, LogStream, Script  # noqa: F401 Script used for tool PYTHONPATH injection
from app.db.session import SessionLocal
from app.services.config_injector_service import cleanup_config, create_config

logger = logging.getLogger(__name__)

# Path where the pending queue is persisted across restarts
_QUEUE_STATE_PATH = settings.data_dir / "queue_state.json"


class ScriptAlreadyRunningError(RuntimeError):
    """
    Raised when a cron or manual trigger tries to queue a script that already
    has a QUEUED execution pending.

    Conduit allows one in-flight run + one queued run per script at a time.
    Accepting more would cause unbounded queue growth for frequently-firing crons.
    If the script is only RUNNING (no queued run yet), the new trigger is queued
    automatically and runs as soon as the current execution finishes.
    """

    def __init__(self, script_id: str, existing_execution_id: str, status: str) -> None:
        self.script_id = script_id
        self.existing_execution_id = existing_execution_id
        self.status = status
        super().__init__(
            f"Script already has a queued execution ({existing_execution_id}). "
            f"The pending run will start once the current execution finishes."
        )


class RunnerService:
    """
    Manages script subprocess execution with concurrency control and graceful shutdown.
    """

    def __init__(self) -> None:
        # execution_id → asyncio subprocess Process
        self._running_procs: Dict[str, asyncio.subprocess.Process] = {}
        # execution_id → asyncio Task managing the run
        self._running_tasks: Dict[str, asyncio.Task] = {}
        # Pending queue: deque of (execution_id, script_id) tuples
        self._queue: Deque[Tuple[str, str]] = deque()
        # Set of script_ids that are currently executing (for per-script single-instance tracking)
        self._running_script_ids: set = set()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run_script(self, script_id: str, db: Session) -> str:
        """
        Trigger a script run.

        Enforces single-instance execution: rejects the request with
        ScriptAlreadyRunningError if another execution of the same script is
        already running or queued.

        If under the concurrency limit, starts immediately. Otherwise queues it.

        Args:
            script_id: ID of the script to run.
            db: SQLAlchemy session (used only to create the Execution row).

        Returns:
            The new execution_id.

        Raises:
            ScriptAlreadyRunningError: If the script already has a running or
                queued execution.
        """
        # Per-script queue guard: allow at most one QUEUED run per script.
        # (Running → queue the new one; already queued → reject to prevent pile-up.)
        already_queued = (
            db.query(Execution)
            .filter(
                Execution.script_id == script_id,
                Execution.status == ExecutionStatus.QUEUED,
            )
            .first()
        )
        if already_queued:
            raise ScriptAlreadyRunningError(
                script_id=script_id,
                existing_execution_id=already_queued.id,
                status=already_queued.status.value,
            )

        execution_id = str(uuid.uuid4())

        # Determine whether to start immediately or queue:
        #   • Script already running → queue so it runs sequentially after current run
        #   • At concurrency limit  → queue until a slot opens
        #   • Otherwise            → start immediately
        script_is_running = script_id in self._running_script_ids
        at_concurrency_limit = len(self._running_procs) >= settings.max_concurrent_scripts

        status: ExecutionStatus
        if script_is_running or at_concurrency_limit:
            status = ExecutionStatus.QUEUED
            self._queue.append((execution_id, script_id))
            reason = "script already running" if script_is_running else "concurrency limit reached"
            logger.info(
                "Script %s queued (%s, queue depth: %d)", script_id, reason, len(self._queue)
            )
        else:
            status = ExecutionStatus.RUNNING
            self._running_script_ids.add(script_id)

        execution = Execution(
            id=execution_id,
            script_id=script_id,
            status=status,
        )
        db.add(execution)
        db.commit()

        if status == ExecutionStatus.RUNNING:
            task = asyncio.create_task(self._execute(execution_id, script_id))
            self._running_tasks[execution_id] = task

        return execution_id

    async def cancel_script(self, execution_id: str, db: Session) -> None:
        """
        Cancel a running or queued execution.

        Sends SIGTERM to the subprocess if running, or removes from queue.
        """
        # Remove from queue if pending
        cancelled_script_ids = {sid for eid, sid in self._queue if eid == execution_id}
        self._queue = deque(
            item for item in self._queue if item[0] != execution_id
        )

        # Terminate subprocess if running
        proc = self._running_procs.get(execution_id)
        if proc and proc.returncode is None:
            proc.terminate()
            logger.info("Sent SIGTERM to execution %s", execution_id)

        # Clean up per-script tracking for cancelled items
        for sid in cancelled_script_ids:
            # Only discard if no other queued item references this script
            if not any(s == sid for _, s in self._queue):
                self._running_script_ids.discard(sid)

        # Update DB status
        exec_row = db.query(Execution).filter_by(id=execution_id).first()
        if exec_row and exec_row.status in (ExecutionStatus.RUNNING, ExecutionStatus.QUEUED):
            exec_row.status = ExecutionStatus.INTERRUPTED
            exec_row.finished_at = datetime.utcnow()
            db.commit()

    def get_active_executions(self) -> List[str]:
        """Return IDs of currently running executions."""
        return list(self._running_procs.keys())

    def get_queue_depth(self) -> int:
        """Return number of executions waiting to run."""
        return len(self._queue)

    async def shutdown(self) -> None:
        """
        Graceful shutdown:
          1. Terminate all running subprocesses.
          2. Cancel all runner tasks.
          3. Mark running executions as interrupted in the DB.
          4. Persist the pending queue to disk for restore on next startup.
        """
        logger.info(
            "Runner shutdown — terminating %d running, queuing %d pending",
            len(self._running_procs), len(self._queue),
        )

        # Terminate all subprocesses
        for exec_id, proc in list(self._running_procs.items()):
            if proc.returncode is None:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass

        # Brief wait then force-kill anything still alive
        if self._running_procs:
            await asyncio.sleep(3)
            for exec_id, proc in list(self._running_procs.items()):
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass

        # Cancel all runner tasks
        for task in list(self._running_tasks.values()):
            task.cancel()

        if self._running_tasks:
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)

        # Mark running executions as interrupted in DB
        db = SessionLocal()
        try:
            for exec_id in list(self._running_procs.keys()):
                exec_row = db.query(Execution).filter_by(id=exec_id).first()
                if exec_row and exec_row.status == ExecutionStatus.RUNNING:
                    exec_row.status = ExecutionStatus.INTERRUPTED
                    exec_row.finished_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()

        # Persist pending queue to disk
        self._persist_queue()

    async def restore_state(self) -> None:
        """
        Called at startup to recover from a previous shutdown or crash.

          1. Mark any executions still showing as RUNNING as INTERRUPTED
             (they were mid-flight when the process died).
          2. Re-queue any pending executions persisted in queue_state.json.
        """
        db = SessionLocal()
        try:
            # 1. Crash recovery — orphaned RUNNING rows
            orphaned = (
                db.query(Execution)
                .filter(Execution.status == ExecutionStatus.RUNNING)
                .all()
            )
            for row in orphaned:
                row.status = ExecutionStatus.INTERRUPTED
                row.finished_at = datetime.utcnow()
            if orphaned:
                db.commit()
                logger.warning(
                    "Marked %d orphaned running executions as interrupted", len(orphaned)
                )

            # 2. Restore persisted queue
            if _QUEUE_STATE_PATH.exists():
                try:
                    items = json.loads(_QUEUE_STATE_PATH.read_text())
                    for item in items:
                        self._queue.append((item["execution_id"], item["script_id"]))
                    _QUEUE_STATE_PATH.unlink()
                    logger.info(
                        "Restored %d queued executions from queue_state.json", len(items)
                    )

                    # Start processing the restored queue
                    await self._drain_queue(db)
                except Exception as exc:
                    logger.error("Failed to restore queue state: %s", exc)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Internal — execution lifecycle
    # ------------------------------------------------------------------

    async def _execute(self, execution_id: str, script_id: str) -> None:
        """
        Full lifecycle for one script run. Runs as an asyncio Task.
        Creates its own DB session — the caller's session may be closed by the time
        this task runs.
        """
        db = SessionLocal()
        config_path: Optional[Path] = None

        try:
            # Fetch the script record
            script = db.query(Script).filter_by(id=script_id).first()
            if not script:
                logger.error("Script %s not found — cannot execute", script_id)
                self._fail_execution(execution_id, None, "Script record not found in database", db)
                return

            # Build the secure temp config file
            config_path = create_config(execution_id, script, db)

            # Build a PYTHONPATH that includes all enabled tool directories.
            # Each tool lives in data/tools/{id}/{name}.py — its parent dir is
            # added to PYTHONPATH so scripts can do ``import {name}``.
            tool_scripts = (
                db.query(Script)
                .filter(Script.script_type == "tool", Script.enabled.is_(True))
                .all()
            )
            tool_dirs = [str(Path(t.file_path).parent) for t in tool_scripts]
            env = os.environ.copy()
            if tool_dirs:
                existing = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = os.pathsep.join(tool_dirs + ([existing] if existing else []))

            # Spawn the subprocess.
            # cwd is pinned to the script's own directory so that relative-path
            # file operations (open('data.csv'), os.listdir('.'), etc.) resolve
            # within the script folder rather than leaking the host working dir.
            script_cwd = str(Path(script.file_path).parent)
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    script.file_path,
                    f"--conduit-config={config_path}",
                    f"--conduit-execution-id={execution_id}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=script_cwd,
                    env=env,
                )
            except Exception as exc:
                logger.error("Failed to spawn script %s: %s", script_id, exc)
                self._fail_execution(execution_id, None, f"Failed to start: {exc}", db)
                return

            self._running_procs[execution_id] = proc
            logger.info("Started execution %s (script=%s, pid=%d)", execution_id, script_id, proc.pid)

            # Collect stdout and stderr into buffers (written to DB after exit)
            stdout_lines: List[Tuple[datetime, str]] = []
            stderr_lines: List[Tuple[datetime, str]] = []

            stdout_task = asyncio.create_task(
                self._collect_output(proc.stdout, stdout_lines)
            )
            stderr_task = asyncio.create_task(
                self._collect_output(proc.stderr, stderr_lines)
            )

            # Wait for process to finish, respecting optional timeout
            status = ExecutionStatus.SUCCESS
            return_code: Optional[int] = None

            try:
                timeout = float(script.timeout_seconds) if script.timeout_seconds else None
                if timeout:
                    await asyncio.wait_for(proc.wait(), timeout=timeout)
                else:
                    await proc.wait()

                return_code = proc.returncode
                status = ExecutionStatus.SUCCESS if return_code == 0 else ExecutionStatus.FAILED

            except asyncio.TimeoutError:
                logger.warning("Execution %s timed out after %ss", execution_id, script.timeout_seconds)
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                return_code = proc.returncode
                status = ExecutionStatus.TIMEOUT

            # Wait for output buffers to flush
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

            # Persist logs
            for ts, content in stdout_lines:
                db.add(ExecutionLog(
                    execution_id=execution_id,
                    stream=LogStream.STDOUT,
                    content=content,
                    timestamp=ts,
                ))
            for ts, content in stderr_lines:
                db.add(ExecutionLog(
                    execution_id=execution_id,
                    stream=LogStream.STDERR,
                    content=content,
                    timestamp=ts,
                ))

            # Update execution record
            exec_row = db.query(Execution).filter_by(id=execution_id).first()
            if exec_row:
                exec_row.status = status
                exec_row.return_code = return_code
                exec_row.finished_at = datetime.utcnow()
            db.commit()

            logger.info(
                "Execution %s finished — status=%s return_code=%s",
                execution_id, status.value, return_code,
            )

        except asyncio.CancelledError:
            # Shutdown was called — mark interrupted and re-raise
            exec_row = db.query(Execution).filter_by(id=execution_id).first()
            if exec_row:
                exec_row.status = ExecutionStatus.INTERRUPTED
                exec_row.finished_at = datetime.utcnow()
                db.commit()
            raise

        except Exception as exc:
            logger.exception("Unexpected error in execution %s: %s", execution_id, exc)
            exec_row = db.query(Execution).filter_by(id=execution_id).first()
            if exec_row:
                exec_row.status = ExecutionStatus.FAILED
                exec_row.finished_at = datetime.utcnow()
                db.add(ExecutionLog(
                    execution_id=execution_id,
                    stream=LogStream.STDERR,
                    content=f"Internal runner error: {exc}",
                ))
                db.commit()

        finally:
            # Always clean up the config file and release the slot
            if config_path:
                cleanup_config(execution_id)
            self._running_procs.pop(execution_id, None)
            self._running_tasks.pop(execution_id, None)
            self._running_script_ids.discard(script_id)
            db.close()

            # Start the next queued execution if any
            next_db = SessionLocal()
            try:
                await self._drain_queue(next_db)
            finally:
                next_db.close()

    async def _collect_output(
        self,
        reader: asyncio.StreamReader,
        buffer: List[Tuple[datetime, str]],
    ) -> None:
        """Read lines from a subprocess stream and append to a buffer."""
        async for line in reader:
            ts = datetime.utcnow()
            content = line.decode(errors="replace").rstrip("\n\r")
            if content:  # Skip empty lines
                buffer.append((ts, content))

    def _fail_execution(
        self,
        execution_id: str,
        return_code: Optional[int],
        message: str,
        db: Session,
    ) -> None:
        """Mark an execution as failed and log the reason."""
        exec_row = db.query(Execution).filter_by(id=execution_id).first()
        if exec_row:
            exec_row.status = ExecutionStatus.FAILED
            exec_row.return_code = return_code
            exec_row.finished_at = datetime.utcnow()
            db.add(ExecutionLog(
                execution_id=execution_id,
                stream=LogStream.STDERR,
                content=message,
            ))
            db.commit()

    async def _drain_queue(self, db: Session) -> None:
        """
        Start queued executions up to the concurrency limit.

        Respects per-script sequential execution: if the next queued item's
        script is still running (e.g. a cron-triggered second run waiting for
        the first to finish), it is moved to the back of the queue and the next
        candidate is tried instead. We attempt at most len(queue) pops per call
        to prevent an infinite loop when all queued scripts are still running.
        """
        attempts = len(self._queue)
        while self._queue and len(self._running_procs) < settings.max_concurrent_scripts and attempts > 0:
            execution_id, script_id = self._queue.popleft()
            attempts -= 1

            if script_id in self._running_script_ids:
                # This script's previous run hasn't finished yet — hold it back.
                self._queue.append((execution_id, script_id))
                logger.debug(
                    "Skipping queued execution %s — script %s still running",
                    execution_id, script_id,
                )
                continue

            exec_row = db.query(Execution).filter_by(id=execution_id).first()
            if exec_row:
                exec_row.status = ExecutionStatus.RUNNING
                db.commit()

            self._running_script_ids.add(script_id)
            task = asyncio.create_task(self._execute(execution_id, script_id))
            self._running_tasks[execution_id] = task
            logger.info(
                "Dequeued execution %s (script=%s, queue remaining: %d)",
                execution_id, script_id, len(self._queue),
            )

    def _persist_queue(self) -> None:
        """Write the pending queue to disk for restore on next startup."""
        items = [
            {"execution_id": exec_id, "script_id": script_id}
            for exec_id, script_id in self._queue
        ]
        try:
            _QUEUE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _QUEUE_STATE_PATH.write_text(json.dumps(items))
            if items:
                logger.info("Persisted %d queued executions to queue_state.json", len(items))
        except Exception as exc:
            logger.error("Failed to persist queue state: %s", exc)


# Exported singleton
runner_service = RunnerService()
