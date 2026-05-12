"""
Pip package management — install, uninstall, and list Python packages
in the environment that runs scripts.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/packages", tags=["packages"])

# Allowlist of characters in a package spec (name, version, extras).
# Covers: letters, digits, -_.[]<>=!,;~@ and whitespace.
# Rejects shell metacharacters that have no place in a pip spec.
_SAFE_PKG = re.compile(r'^[\w\s\-_.+\[\]<>=!,;~@:/]+$')


def _run_pip(*args: str, timeout: int = 300) -> Dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "pip", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[Dict[str, str]])
def list_packages():
    """Return all packages installed in the current Python environment."""
    result = _run_pip("list", "--format=json", timeout=30)
    if result["returncode"] != 0:
        raise HTTPException(status_code=500, detail=result["stderr"] or "pip list failed")
    packages = json.loads(result["stdout"])
    return sorted(packages, key=lambda p: p["name"].lower())


class InstallRequest(BaseModel):
    package: str


@router.post("/install")
def install_package(body: InstallRequest):
    """Install a pip package. Accepts any valid pip install spec (e.g. 'requests>=2.28')."""
    pkg = body.package.strip()
    if not pkg:
        raise HTTPException(status_code=422, detail="Package name is required")
    if not _SAFE_PKG.match(pkg):
        raise HTTPException(status_code=422, detail="Invalid package specification")

    result = _run_pip("install", pkg)
    output = (result["stdout"] + result["stderr"]).strip()
    return {"success": result["returncode"] == 0, "output": output}


@router.delete("/{name}")
def uninstall_package(name: str):
    """Uninstall a pip package by name."""
    name = name.strip()
    if not name or not _SAFE_PKG.match(name):
        raise HTTPException(status_code=422, detail="Invalid package name")

    result = _run_pip("uninstall", "-y", name)
    output = (result["stdout"] + result["stderr"]).strip()
    return {"success": result["returncode"] == 0, "output": output}
