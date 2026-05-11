"""
Metrics service — system health collection and threshold alerting.

Metrics are collected every N seconds (default: 30) via a background asyncio task.
All values are stored as fractions (0.0–1.0) to align with threshold settings.
Rows older than 30 days are pruned on each collection cycle.

Threshold crossing logic:
  - Compares current value to the previous reading for that metric.
  - A notification is created only when crossing FROM below TO above a threshold.
  - No duplicate notifications while the value stays above threshold.
  - Crossing back down then back up creates a new notification.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import psutil
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ExecutionStatus, NotificationLevel, SystemMetric
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_metrics_task: Optional[asyncio.Task] = None

# Metrics subject to threshold evaluation
_THRESHOLD_METRICS = ["cpu_percent", "memory_percent", "disk_percent", "failed_rate_1h"]

# Network counter snapshot from the previous sample (used to compute deltas)
_last_net_snapshot: Optional[tuple[float, int, int]] = None  # (timestamp, bytes_recv, bytes_sent)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def collect_metrics(db: Session) -> Dict[str, float]:
    """
    Sample current system metrics and persist them to the database.

    All percentage values are stored as fractions (0.0–1.0).

    Returns:
        Dict with keys: cpu_percent, memory_percent, disk_percent,
        active_scripts, queue_depth, failed_rate_1h.
    """
    # Lazily import runner_service to avoid circular imports at module load
    from app.services.runner_service import runner_service

    global _last_net_snapshot
    import time as _time

    cpu = psutil.cpu_percent(interval=None) / 100.0
    memory = psutil.virtual_memory().percent / 100.0
    disk_usage = psutil.disk_usage(str(settings.data_dir))
    disk = disk_usage.percent / 100.0
    disk_used_gb = disk_usage.used  / (1024 ** 3)
    disk_free_gb = disk_usage.free  / (1024 ** 3)
    active = float(len(runner_service.get_active_executions()))
    queue_depth = float(runner_service.get_queue_depth())
    failed_rate = _compute_failed_rate_1h(db)

    # Network rate (MB since last sample)
    net = psutil.net_io_counters()
    now_ts = _time.time()
    net_recv_mb = 0.0
    net_sent_mb = 0.0
    if _last_net_snapshot is not None:
        prev_ts, prev_recv, prev_sent = _last_net_snapshot
        elapsed = max(now_ts - prev_ts, 0.001)
        # Bytes since last sample (per interval, not per second)
        net_recv_mb = max(net.bytes_recv - prev_recv, 0) / (1024 ** 2)
        net_sent_mb = max(net.bytes_sent - prev_sent, 0) / (1024 ** 2)
    _last_net_snapshot = (now_ts, net.bytes_recv, net.bytes_sent)

    metrics = {
        "cpu_percent": cpu,
        "memory_percent": memory,
        "disk_percent": disk,
        "disk_used_gb": disk_used_gb,
        "disk_free_gb": disk_free_gb,
        "active_scripts": active,
        "queue_depth": queue_depth,
        "failed_rate_1h": failed_rate,
        "network_recv_mb": net_recv_mb,
        "network_sent_mb": net_sent_mb,
    }

    # Persist each metric as its own row
    now = datetime.utcnow()
    for name, value in metrics.items():
        db.add(SystemMetric(metric_name=name, value=value, recorded_at=now))
    db.commit()

    logger.debug(
        "Metrics collected — cpu=%.1f%% mem=%.1f%% disk=%.1f%% active=%d queue=%d failed_1h=%.1f%%",
        cpu * 100, memory * 100, disk * 100, int(active), int(queue_depth), failed_rate * 100,
    )
    return metrics


def _compute_failed_rate_1h(db: Session) -> float:
    """Return the fraction of executions that failed in the last hour."""
    from app.db.models import Execution

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    total = (
        db.query(Execution)
        .filter(Execution.started_at >= one_hour_ago)
        .count()
    )
    if total == 0:
        return 0.0

    failed = (
        db.query(Execution)
        .filter(
            Execution.started_at >= one_hour_ago,
            Execution.status.in_([ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT]),
        )
        .count()
    )
    return failed / total


# ---------------------------------------------------------------------------
# Threshold evaluation
# ---------------------------------------------------------------------------


def evaluate_thresholds(metrics: Dict[str, float], db: Session) -> None:
    """
    Check each threshold metric for a fresh crossing and emit a notification.

    A "fresh crossing" means the previous recorded value was below the threshold
    and the current value is at or above it. This prevents duplicate notifications
    while a metric stays elevated.
    """
    from app.services.notifications_service import create_notification

    for metric_name in _THRESHOLD_METRICS:
        current_value = metrics.get(metric_name, 0.0)

        # Get the second-to-last reading (the one before the current collection)
        prev_metric = (
            db.query(SystemMetric)
            .filter(SystemMetric.metric_name == metric_name)
            .order_by(SystemMetric.recorded_at.desc(), SystemMetric.id.desc())
            .offset(1)
            .first()
        )
        prev_value = prev_metric.value if prev_metric else 0.0

        crit = settings.critical_threshold
        warn = settings.warn_threshold

        if prev_value < crit <= current_value:
            create_notification(
                level=NotificationLevel.CRITICAL,
                category="system_health",
                message=(
                    f"{metric_name.replace('_', ' ').title()} is critical: "
                    f"{current_value:.1%} (threshold: {crit:.0%})"
                ),
                metadata={"metric": metric_name, "value": current_value, "threshold": crit},
                db=db,
            )
        elif prev_value < warn <= current_value < crit:
            create_notification(
                level=NotificationLevel.WARN,
                category="system_health",
                message=(
                    f"{metric_name.replace('_', ' ').title()} is elevated: "
                    f"{current_value:.1%} (threshold: {warn:.0%})"
                ),
                metadata={"metric": metric_name, "value": current_value, "threshold": warn},
                db=db,
            )


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------


def prune_old_metrics(db: Session) -> int:
    """
    Delete SystemMetric rows older than 30 days.

    Returns:
        Number of rows deleted.
    """
    cutoff = datetime.utcnow() - timedelta(days=30)
    deleted = (
        db.query(SystemMetric)
        .filter(SystemMetric.recorded_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    if deleted:
        logger.info("Pruned %d old metric rows (older than 30 days)", deleted)
    return deleted


# ---------------------------------------------------------------------------
# Background loop
# ---------------------------------------------------------------------------


async def _collection_loop() -> None:
    """Background task that collects metrics on a fixed interval."""
    # Brief initial delay so the app is fully started before first collection
    await asyncio.sleep(5)
    while True:
        try:
            db = SessionLocal()
            try:
                metrics = collect_metrics(db)
                evaluate_thresholds(metrics, db)
                prune_old_metrics(db)
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Metrics collection failed: %s", exc, exc_info=True)

        await asyncio.sleep(settings.metrics_interval_seconds)


def start_collection_loop() -> None:
    """
    Start the background metrics collection task.

    Must be called from within an async context (e.g. FastAPI lifespan startup).
    """
    global _metrics_task
    _metrics_task = asyncio.create_task(_collection_loop())
    logger.info(
        "Metrics collection started — interval=%ds", settings.metrics_interval_seconds
    )


def stop_collection_loop() -> None:
    """Cancel the background metrics task on shutdown."""
    global _metrics_task
    if _metrics_task and not _metrics_task.done():
        _metrics_task.cancel()
        logger.info("Metrics collection stopped")
