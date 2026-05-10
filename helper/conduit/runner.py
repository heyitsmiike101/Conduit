"""
conduit.runner — trigger other scripts from within a running script.

Usage:
    from conduit import run_script

    execution = run_script("script-uuid-here")
    print(f"Triggered execution: {execution['execution_id']}")

In dev mode, prints to stdout instead of calling the API.
"""

from __future__ import annotations

import urllib.request
import urllib.error
import json
import warnings

from .config import get_api_base, get_execution_id, is_dev_mode


def run_script(script_id: str) -> dict:
    """
    Trigger another script via the Conduit platform.

    The triggered script is queued independently — this call returns immediately
    without waiting for the other script to complete.

    Args:
        script_id: The UUID of the script to trigger.

    Returns:
        dict with keys:
            execution_id  — the new execution's UUID
            status        — initial status (usually "queued")

    Raises:
        RuntimeWarning (silent) on failure — does not raise exceptions so that
        calling scripts continue running even if the trigger fails.
    """
    if is_dev_mode():
        print(f"[conduit runner] DEV MODE — would trigger script: {script_id}")
        return {"execution_id": "dev-mode-execution", "status": "queued"}

    execution_id = get_execution_id()
    if not execution_id:
        warnings.warn(
            "run_script() called outside of a Conduit execution context",
            RuntimeWarning,
            stacklevel=2,
        )
        return {}

    url = f"{get_api_base()}/internal/trigger-script"
    payload = json.dumps({"script_id": script_id}).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Execution-ID": execution_id,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        warnings.warn(
            f"run_script() failed to trigger '{script_id}': {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return {}
