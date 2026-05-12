"""
Scripts API — CRUD + content editing + version history + injected config + file browser.

Routes:
  GET    /scripts                             — list scripts
  POST   /scripts                             — create script + scaffold file on disk
  GET    /scripts/{id}                        — get one script
  PATCH  /scripts/{id}                        — update script metadata
  DELETE /scripts/{id}                        — delete script + remove disk directory

  GET    /scripts/{id}/content                — read script.py content from disk
  PUT    /scripts/{id}/content                — save new content (auto-creates version)

  GET    /scripts/{id}/versions               — list version history (no code)
  GET    /scripts/{id}/versions/{vid}         — get a single version with code
  POST   /scripts/{id}/versions/{vid}/revert  — revert file to a prior version

  GET    /scripts/{id}/config                 — variables that will be injected at run time

  GET    /scripts/{id}/files                  — list all files in script directory
  GET    /scripts/{id}/files/{path}           — read a file's content
  PUT    /scripts/{id}/files/{path}           — write a file's content (creates if needed)
  POST   /scripts/{id}/files                  — create a new file
  DELETE /scripts/{id}/files/{path}           — delete a file (not script.py)
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.db.models import Script, ScriptPermission, ScriptScope, ScriptVersion, Variable
from app.schemas.scripts import (
    ScriptConfigResponse,
    ScriptContentResponse,
    ScriptContentUpdate,
    ScriptCreate,
    ScriptResponse,
    ScriptUpdate,
    ScriptVariablesUpdate,
    ScriptVersionDetailResponse,
    ScriptVersionResponse,
)
from app.services.encryption_service import get_variable_value

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scripts", tags=["scripts"])

# Starter template written to every new script file
_STARTER_TEMPLATE = '''\
"""
Conduit script — generated automatically.
Edit this file to implement your automation logic.
"""
from conduit import get_config

config = get_config()

# Your code here
print("Hello from Conduit!")
'''

_TOOL_STARTER_TEMPLATE = '''\
"""
Conduit supporting tool — generated automatically.

Import this module in your scripts:

    import {python_name}
    # or
    from {python_name} import my_function

Add shared utilities, helpers, or API clients here.
"""


def example_function(value):
    """Example helper — replace with your own functions."""
    return value
'''


def _resolve_safe_path(base_dir: Path, rel_path: str) -> Path:
    """
    Resolve *rel_path* relative to *base_dir*, preventing path-traversal attacks.
    Raises 400 if the resolved path would escape base_dir.
    """
    try:
        target = (base_dir / rel_path).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not str(target).startswith(str(base_dir.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return target


def _build_file_path(script_id: str, scope: ScriptScope, account_id: Optional[str]) -> Path:
    """Compute the on-disk path for a regular script's main file."""
    if scope == ScriptScope.GLOBAL:
        return settings.data_dir / "scripts" / "global" / script_id / "script.py"
    else:
        return settings.data_dir / "scripts" / "accounts" / account_id / script_id / "script.py"


def _build_tool_file_path(script_id: str, python_name: str) -> Path:
    """Compute the on-disk path for a supporting tool's main file.

    Each tool lives in data/tools/{id}/{python_name}.py.
    data/tools/{id}/ is added to PYTHONPATH at run time so scripts can
    do ``import {python_name}`` to use the tool.
    """
    return settings.data_dir / "tools" / script_id / f"{python_name}.py"


def _scaffold_script_file(file_path: Path) -> None:
    """Create the directory tree, write the starter script, and ensure downloads/ exists."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    (file_path.parent / "downloads").mkdir(exist_ok=True)
    if not file_path.exists():
        file_path.write_text(_STARTER_TEMPLATE)
    logger.info("Scaffolded script file at %s", file_path)


def _scaffold_tool_file(file_path: Path, python_name: str) -> None:
    """Create the directory tree and write the starter tool file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not file_path.exists():
        file_path.write_text(_TOOL_STARTER_TEMPLATE.format(python_name=python_name))
    logger.info("Scaffolded tool file at %s", file_path)


def _get_script_or_404(script_id: str, db: Session) -> Script:
    script = db.query(Script).filter_by(id=script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found")
    return script


def _next_version_number(script_id: str, db: Session) -> int:
    last = (
        db.query(ScriptVersion)
        .filter_by(script_id=script_id)
        .order_by(ScriptVersion.version_number.desc())
        .first()
    )
    return (last.version_number + 1) if last else 1


# ---------------------------------------------------------------------------
# CRUD Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ScriptResponse])
def list_scripts(
    account_id: Optional[str] = None,
    script_type: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[Script]:
    query = db.query(Script)
    if account_id is not None:
        query = query.filter(Script.account_id == account_id)
    if script_type is not None:
        query = query.filter(Script.script_type == script_type)
    return query.order_by(Script.name).all()


@router.post("", response_model=ScriptResponse, status_code=201)
def create_script(body: ScriptCreate, db: Session = Depends(get_db)) -> Script:
    import re
    import uuid

    script_id = str(uuid.uuid4())

    if body.script_type == "tool":
        # Tools are always global — derive a Python-safe module name from the title
        python_name = re.sub(r'[^a-zA-Z0-9]+', '_', body.name).strip('_').lower()
        if python_name and python_name[0].isdigit():
            python_name = 'tool_' + python_name
        python_name = python_name or 'tool'
        file_path = _build_tool_file_path(script_id, python_name)
        scope = ScriptScope.GLOBAL
        account_id = None
    else:
        file_path = _build_file_path(script_id, body.scope, body.account_id)
        scope = body.scope
        account_id = body.account_id

    script = Script(
        id=script_id,
        scope=scope,
        account_id=account_id,
        name=body.name,
        description=body.description,
        file_path=str(file_path),
        timeout_seconds=body.timeout_seconds,
        script_type=body.script_type,
    )
    db.add(script)
    db.flush()

    permission = ScriptPermission(
        script_id=script.id,
        can_read_tables=False,
        can_write_tables=False,
        can_create_tables=False,
    )
    db.add(permission)
    db.commit()
    db.refresh(script)

    if body.script_type == "tool":
        _scaffold_tool_file(file_path, python_name)
    else:
        _scaffold_script_file(file_path)
    return script


@router.get("/{script_id}", response_model=ScriptResponse)
def get_script(script_id: str, db: Session = Depends(get_db)) -> Script:
    return _get_script_or_404(script_id, db)


@router.patch("/{script_id}", response_model=ScriptResponse)
def update_script(
    script_id: str,
    body: ScriptUpdate,
    db: Session = Depends(get_db),
) -> Script:
    script = _get_script_or_404(script_id, db)
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(script, field, value)
    db.commit()
    db.refresh(script)
    return script


@router.delete("/{script_id}", status_code=204)
def delete_script(script_id: str, db: Session = Depends(get_db)) -> None:
    script = _get_script_or_404(script_id, db)
    script_dir = Path(script.file_path).parent
    try:
        if script_dir.exists():
            shutil.rmtree(script_dir)
            logger.info("Removed script directory: %s", script_dir)
    except Exception as exc:
        logger.warning("Failed to remove script directory %s: %s", script_dir, exc)
    db.delete(script)
    db.commit()


# ---------------------------------------------------------------------------
# Content (read/write from disk)
# ---------------------------------------------------------------------------


@router.get("/{script_id}/content", response_model=ScriptContentResponse)
def get_script_content(script_id: str, db: Session = Depends(get_db)) -> dict:
    """Read the script's current source code from disk."""
    script = _get_script_or_404(script_id, db)
    path = Path(script.file_path)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Script file not found on disk: {script.file_path}",
        )
    return {
        "script_id": script_id,
        "file_path": script.file_path,
        "content": path.read_text(encoding="utf-8"),
    }


@router.put("/{script_id}/content", response_model=ScriptVersionDetailResponse)
def save_script_content(
    script_id: str,
    body: ScriptContentUpdate,
    db: Session = Depends(get_db),
) -> ScriptVersion:
    """
    Save new content to disk and snapshot the previous version in the DB.

    Returns the newly created ScriptVersion (the snapshot of what was there
    BEFORE this save — useful for the UI to confirm the version was captured).
    If the file is new/empty, the snapshot records the starter template.
    """
    script = _get_script_or_404(script_id, db)
    path = Path(script.file_path)

    # Read current content (will be the snapshot)
    old_content = path.read_text(encoding="utf-8") if path.exists() else _STARTER_TEMPLATE

    # Save snapshot of old content
    version = ScriptVersion(
        script_id=script_id,
        version_number=_next_version_number(script_id, db),
        code=old_content,
        label=body.label,
        file_path=path.name,
    )
    db.add(version)

    # Write new content to disk
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    logger.info("Script %s content updated — version %d created", script_id, version.version_number)

    db.commit()
    db.refresh(version)
    return version


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------


@router.get("/{script_id}/versions", response_model=list[ScriptVersionResponse])
def list_script_versions(script_id: str, db: Session = Depends(get_db)) -> List[ScriptVersion]:
    """List all version snapshots for a script, newest first. Code not included."""
    _get_script_or_404(script_id, db)
    return (
        db.query(ScriptVersion)
        .filter_by(script_id=script_id)
        .order_by(ScriptVersion.version_number.desc())
        .all()
    )


@router.get("/{script_id}/versions/{version_id}", response_model=ScriptVersionDetailResponse)
def get_script_version(
    script_id: str,
    version_id: str,
    db: Session = Depends(get_db),
) -> ScriptVersion:
    """Fetch a specific version including its code."""
    _get_script_or_404(script_id, db)
    version = db.query(ScriptVersion).filter_by(id=version_id, script_id=script_id).first()
    if not version:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
    return version


@router.post("/{script_id}/versions/{version_id}/revert", response_model=ScriptVersionDetailResponse)
def revert_script_to_version(
    script_id: str,
    version_id: str,
    db: Session = Depends(get_db),
) -> ScriptVersion:
    """
    Revert the script's on-disk file to a prior version.

    Snapshots the current content first (so the revert itself is undoable),
    then writes the chosen version's code to disk.
    Returns the new snapshot (of the content that was just replaced).
    """
    script = _get_script_or_404(script_id, db)
    target = db.query(ScriptVersion).filter_by(id=version_id, script_id=script_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")

    # Determine which file to revert — use the version's file_path, fall back to main script
    script_dir = Path(script.file_path).parent
    rel_path = target.file_path if target.file_path else Path(script.file_path).name
    path = _resolve_safe_path(script_dir, rel_path)

    old_content = path.read_text(encoding="utf-8") if path.exists() else ""

    # Snapshot current content before overwriting
    snapshot = ScriptVersion(
        script_id=script_id,
        version_number=_next_version_number(script_id, db),
        code=old_content,
        label=f"Before revert to v{target.version_number}",
        file_path=rel_path,
    )
    db.add(snapshot)

    # Write the target version to disk
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(target.code, encoding="utf-8")
    logger.info("Script %s reverted to version %d (%s)", script_id, target.version_number, rel_path)

    db.commit()
    db.refresh(snapshot)
    return snapshot


# ---------------------------------------------------------------------------
# Injected config (variables visible to this script)
# ---------------------------------------------------------------------------


@router.get("/{script_id}/config", response_model=ScriptConfigResponse)
def get_script_config(script_id: str, db: Session = Depends(get_db)) -> dict:
    """
    Return ALL variables accessible to this script with a 'selected' flag.
    selected=True means the variable will be injected at run time.
    If script.selected_variable_ids is null, all vars are selected.
    Values are masked for api_key types.
    """
    import json as _json
    script = _get_script_or_404(script_id, db)

    # Parse the selection list (null → all selected)
    selected_ids: Optional[set] = None
    if script.selected_variable_ids is not None:
        try:
            selected_ids = set(_json.loads(script.selected_variable_ids))
        except Exception:
            selected_ids = None

    def _serialize(var: Variable) -> dict:
        is_api_key = var.variable_type == "api_key"
        is_masked = var.is_secret or is_api_key
        is_selected = (selected_ids is None) or (var.id in selected_ids)
        return {
            "id": var.id,
            "name": var.name,
            "value": "***" if is_masked else get_variable_value(var, reveal_secret=False),
            "is_secret": var.is_secret,
            "variable_type": var.variable_type,
            "selected": is_selected,
        }

    global_vars = (
        db.query(Variable)
        .filter_by(scope="global")
        .order_by(Variable.name)
        .all()
    )
    account_vars = []
    if script.account_id:
        account_vars = (
            db.query(Variable)
            .filter_by(scope="account", account_id=script.account_id)
            .order_by(Variable.name)
            .all()
        )

    return {
        "selected_variable_ids": list(selected_ids) if selected_ids is not None else None,
        "global_vars": [_serialize(v) for v in global_vars],
        "account_vars": [_serialize(v) for v in account_vars],
    }


@router.put("/{script_id}/variables", response_model=ScriptResponse)
def set_script_variables(
    script_id: str,
    body: ScriptVariablesUpdate,
    db: Session = Depends(get_db),
) -> Script:
    """
    Set which variables are injected into this script at run time.
    Pass selected_variable_ids=null to inject all (default).
    Pass an empty list [] to inject none.
    """
    import json as _json
    script = _get_script_or_404(script_id, db)
    if body.selected_variable_ids is None:
        script.selected_variable_ids = None
    else:
        script.selected_variable_ids = _json.dumps(body.selected_variable_ids)
    db.commit()
    db.refresh(script)
    return script


# ---------------------------------------------------------------------------
# File browser — list / read / write / create / delete files in script dir
# ---------------------------------------------------------------------------


class ScriptFileWrite(BaseModel):
    """Body for PUT /files/{path} — write a file."""
    content: str


class ScriptFileCreate(BaseModel):
    """Body for POST /files — create a new file."""
    filename: str   # relative path within the script directory
    content: str = ""


@router.get("/{script_id}/files", response_model=List[Dict[str, Any]])
def list_script_files(script_id: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    List all files inside the script's on-disk directory.

    Returns a list of dicts: [{path, size, modified_at}] sorted so script.py
    appears first, everything else alphabetically.
    """
    script = _get_script_or_404(script_id, db)
    script_dir = Path(script.file_path).parent
    if not script_dir.exists():
        return []

    entries: List[Dict[str, Any]] = []
    for f in script_dir.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(script_dir))
        stat = f.stat()
        entries.append({
            "path": rel,
            "size": stat.st_size,
            "modified_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
        })

    # script.py first, then alphabetical
    entries.sort(key=lambda e: (0 if e["path"] == "script.py" else 1, e["path"]))
    return entries


@router.get("/{script_id}/files/{file_path:path}")
def get_script_file(
    script_id: str,
    file_path: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Read the text content of a file in the script directory."""
    script = _get_script_or_404(script_id, db)
    script_dir = Path(script.file_path).parent
    target = _resolve_safe_path(script_dir, file_path)

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"File '{file_path}' not found")

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail=f"'{file_path}' is a binary file and cannot be opened in the editor",
        )

    return {
        "path": file_path,
        "content": content,
        "size": target.stat().st_size,
        "modified_at": datetime.utcfromtimestamp(target.stat().st_mtime).isoformat(),
    }


@router.put("/{script_id}/files/{file_path:path}", status_code=204)
def save_script_file(
    script_id: str,
    file_path: str,
    body: ScriptFileWrite,
    db: Session = Depends(get_db),
) -> None:
    """
    Write content to a file in the script directory.
    Creates the file (and any parent subdirectories) if it doesn't exist.
    Creates a version snapshot for any text file so history is tracked.
    """
    script = _get_script_or_404(script_id, db)
    script_dir = Path(script.file_path).parent
    target = _resolve_safe_path(script_dir, file_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Snapshot the previous content before overwriting (version history for all files)
    old_content = target.read_text(encoding="utf-8") if target.exists() else ""
    version = ScriptVersion(
        script_id=script_id,
        version_number=_next_version_number(script_id, db),
        code=old_content,
        file_path=file_path,
    )
    db.add(version)

    target.write_text(body.content, encoding="utf-8")
    db.commit()
    logger.info("Script %s — wrote file %s (%d bytes)", script_id, file_path, len(body.content))


@router.post("/{script_id}/files", status_code=201)
def create_script_file(
    script_id: str,
    body: ScriptFileCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Create a new file in the script directory.
    Returns 409 if the file already exists.
    """
    script = _get_script_or_404(script_id, db)
    script_dir = Path(script.file_path).parent
    target = _resolve_safe_path(script_dir, body.filename)

    if target.exists():
        raise HTTPException(status_code=409, detail=f"File '{body.filename}' already exists")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")
    logger.info("Script %s — created file %s", script_id, body.filename)

    return {
        "path": body.filename,
        "size": target.stat().st_size,
        "modified_at": datetime.utcfromtimestamp(target.stat().st_mtime).isoformat(),
    }


@router.delete("/{script_id}/files/{file_path:path}", status_code=204)
def delete_script_file(
    script_id: str,
    file_path: str,
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a file from the script directory.
    Returns 400 if trying to delete script.py (the main entry point).
    """
    if file_path == "script.py":
        raise HTTPException(status_code=400, detail="Cannot delete the main script file (script.py)")

    script = _get_script_or_404(script_id, db)
    script_dir = Path(script.file_path).parent
    target = _resolve_safe_path(script_dir, file_path)

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File '{file_path}' not found")

    target.unlink()
    logger.info("Script %s — deleted file %s", script_id, file_path)


@router.post("/{script_id}/upload", status_code=201)
async def upload_script_file_binary(
    script_id: str,
    path: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Upload any file (binary or text) to the script directory via multipart form.

    Unlike PUT /files/{path} which expects a JSON body with text content,
    this endpoint accepts raw bytes so binary files (images, PDFs, compiled
    artifacts, etc.) are stored without corruption.

    Form fields:
        path  — relative destination path within the script directory
        file  — the file data (multipart)
    """
    script = _get_script_or_404(script_id, db)
    script_dir = Path(script.file_path).parent
    target = _resolve_safe_path(script_dir, path)
    target.parent.mkdir(parents=True, exist_ok=True)

    contents = await file.read()
    target.write_bytes(contents)
    logger.info(
        "Script %s — uploaded binary file %s (%d bytes)", script_id, path, len(contents)
    )
    return {
        "path": path,
        "size": len(contents),
        "modified_at": datetime.utcfromtimestamp(target.stat().st_mtime).isoformat(),
    }


# ---------------------------------------------------------------------------
# Downloads — files placed in {script_dir}/downloads/ by the script at runtime
# ---------------------------------------------------------------------------


@router.get("/{script_id}/downloads", response_model=List[Dict[str, Any]])
def list_downloads(script_id: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    List files in the script's downloads/ subdirectory.
    Returns an empty list if the directory doesn't exist yet.
    Files are sorted newest-first by modification time.
    """
    script = _get_script_or_404(script_id, db)
    downloads_dir = Path(script.file_path).parent / "downloads"
    downloads_dir.mkdir(exist_ok=True)

    files = []
    for f in downloads_dir.rglob("*"):
        if not f.is_file():
            continue
        stat = f.stat()
        files.append({
            "name": str(f.relative_to(downloads_dir)),
            "size": stat.st_size,
            "modified_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
        })

    files.sort(key=lambda f: f["modified_at"], reverse=True)
    return files


@router.get("/{script_id}/downloads/{filename:path}")
def get_download(
    script_id: str,
    filename: str,
    inline: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    """
    Serve a file from the script's downloads/ directory.

    ?inline=true  — Content-Disposition: inline  (browser renders in-tab, good for preview)
    ?inline=false — Content-Disposition: attachment (forces download, default)
    """
    script = _get_script_or_404(script_id, db)
    downloads_dir = Path(script.file_path).parent / "downloads"
    target = _resolve_safe_path(downloads_dir, filename)

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Download '{filename}' not found")

    return FileResponse(
        str(target),
        filename=target.name,
        content_disposition_type="inline" if inline else "attachment",
    )
