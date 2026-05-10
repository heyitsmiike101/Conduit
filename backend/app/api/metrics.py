"""
Metrics API — historical system metric data.

Routes:
  GET /metrics   — return metric samples for the last N hours, grouped by metric name.
                   Used by the dashboard to render 24-hour sparkline charts.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import SystemMetric

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def get_metrics(
    hours: int = 24,
    db: Session = Depends(get_db),
) -> Dict[str, List[dict]]:
    """
    Return system metric samples collected in the last `hours` hours.

    Response shape:
    {
      "cpu_percent":    [{"value": 0.12, "recorded_at": "2026-05-07T10:00:00"}, ...],
      "memory_percent": [...],
      "disk_percent":   [...],
      "disk_used_gb":   [...],
      "network_sent_mb":[...],
      "network_recv_mb":[...],
    }

    Only metric names that have at least one sample in the window are included.
    Samples are ordered oldest-first so charting libraries can plot them directly.
    """
    cutoff = datetime.utcnow() - timedelta(hours=max(1, min(hours, 168)))  # cap at 7 days

    rows = (
        db.query(SystemMetric)
        .filter(SystemMetric.recorded_at >= cutoff)
        .order_by(SystemMetric.recorded_at.asc())
        .all()
    )

    result: Dict[str, List[dict]] = {}
    for row in rows:
        bucket = result.setdefault(row.metric_name, [])
        bucket.append({
            "value": row.value,
            "recorded_at": row.recorded_at.isoformat(),
        })

    return result
