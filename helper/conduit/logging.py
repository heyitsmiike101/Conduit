"""
API call logging for Conduit-managed scripts.

In production mode: sends a POST to the internal /log-api-call endpoint so
the call appears in the execution log alongside stdout/stderr.

In dev mode (CONDUIT_DEV_MODE=1): prints to stdout instead — no HTTP call.

Usage:
    from conduit import log_api_call
    log_api_call(method="GET", url="https://api.example.com/data",
                 status_code=200, duration_ms=142.5)
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, Optional


def log_api_call(
    *,
    method: str,
    url: str,
    status_code: int,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record an outbound HTTP call in the execution log.

    In production: sends to the backend's internal /log-api-call endpoint.
    In dev mode: prints to stdout with a [conduit api] prefix.

    Logging failure is never fatal — errors emit a RuntimeWarning.

    Args:
        method: HTTP method used (e.g. "GET", "POST").
        url: Full URL that was called.
        status_code: Response status code received.
        duration_ms: Round-trip time in milliseconds. Defaults to 0.0 if not provided.
        metadata: Optional dict of extra context (e.g. error message, response size).
    """
    from .config import get_api_base, get_execution_id, is_dev_mode

    ms = duration_ms or 0.0

    if is_dev_mode():
        # Dev mode: just print — no HTTP needed
        meta_str = f" | {metadata}" if metadata else ""
        print(f"[conduit api] {method} {url} → {status_code} ({ms:.1f}ms){meta_str}")
        return

    execution_id = get_execution_id()
    if not execution_id:
        warnings.warn(
            "Conduit: log_api_call() called outside a Conduit execution — call not sent.",
            RuntimeWarning,
            stacklevel=2,
        )
        return

    try:
        import httpx
        resp = httpx.post(
            f"{get_api_base()}/internal/log-api-call",
            json={
                "method": method,
                "url": url,
                "status_code": status_code,
                "duration_ms": ms,
                "metadata": metadata,
            },
            headers={"X-Execution-ID": execution_id},
            timeout=5.0,
        )
        if resp.status_code not in (200, 204):
            warnings.warn(
                f"Conduit: log_api_call() received unexpected status {resp.status_code}",
                RuntimeWarning,
                stacklevel=2,
            )
    except Exception as exc:
        warnings.warn(
            f"Conduit: log_api_call() failed to reach backend: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
