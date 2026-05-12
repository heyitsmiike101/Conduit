"""
Config injector service.

Builds the secure temporary config file passed to each script run via CLI arg.
The file contains all decrypted variable values for the script's scope.

Security requirements (non-negotiable):
  - File written with chmod 600 (owner read/write only)
  - File deleted immediately after the script exits (success, failure, or crash)
  - Never logged — secrets inside must not appear in any log output
  - Path passed as CLI arg (not env var) to avoid ps aux exposure
"""

from __future__ import annotations

import json
import logging
import stat
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import EncryptionError
from app.db.models import Script, ScriptScope, Variable
from app.services.encryption_service import decrypt_variable

logger = logging.getLogger(__name__)


def create_config(execution_id: str, script: Script, db: Session) -> Path:
    """
    Build and write the temp config file for a script run.

    Queries all variables in scope (global always included; account variables
    included if the script is account-scoped). If the script has a non-null
    selected_variable_ids JSON array, only variables in that list are injected.
    Account variables with the same name as global variables take precedence.

    Args:
        execution_id: Used to build a unique temp filename.
        script: The Script ORM object (used to determine variable scope).
        db: SQLAlchemy session.

    Returns:
        Path to the written config file (mode 600).
    """
    # Parse the per-script variable selection (null/missing = inject all)
    selected_ids: Optional[set[str]] = None
    if script.selected_variable_ids:
        try:
            selected_ids = set(json.loads(script.selected_variable_ids))
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "Script %s has invalid selected_variable_ids JSON — defaulting to all",
                script.id,
            )
            selected_ids = None

    # Collect global variables
    global_vars = (
        db.query(Variable)
        .filter(Variable.scope == ScriptScope.GLOBAL)
        .all()
    )

    # Collect account variables if applicable
    account_vars: list[Variable] = []
    if script.scope == ScriptScope.ACCOUNT and script.account_id:
        account_vars = (
            db.query(Variable)
            .filter(
                Variable.scope == ScriptScope.ACCOUNT,
                Variable.account_id == script.account_id,
            )
            .all()
        )

    # Apply selection filter (None = include all)
    if selected_ids is not None:
        global_vars = [v for v in global_vars if v.id in selected_ids]
        account_vars = [v for v in account_vars if v.id in selected_ids]

    # Build config dict — account vars override global vars of the same name.
    # Unreadable variables (wrong key) are skipped with a warning so one bad
    # variable doesn't prevent all scripts from running.
    config: dict[str, str] = {}
    bad_vars: list[str] = []
    for var in global_vars:
        try:
            config[var.name] = decrypt_variable(var.value_encrypted)
        except EncryptionError:
            bad_vars.append(var.name)
            logger.warning("Cannot decrypt variable '%s' (id=%s) — skipping", var.name, var.id)
    for var in account_vars:
        try:
            config[var.name] = decrypt_variable(var.value_encrypted)
        except EncryptionError:
            bad_vars.append(var.name)
            logger.warning("Cannot decrypt variable '%s' (id=%s) — skipping", var.name, var.id)

    if bad_vars:
        names = ", ".join(bad_vars)
        raise EncryptionError(
            f"The following variable(s) could not be decrypted and need to be re-saved: {names}. "
            "This usually means the encryption key changed since the variable was created. "
            "Edit each variable and save a new value to fix this."
        )

    # Write to a uniquely-named temp file
    tmp_dir = settings.data_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"run_{execution_id}.json"

    tmp_path.write_text(json.dumps(config), encoding="utf-8")
    tmp_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600

    logger.debug(
        "Config written for execution %s (%d variables)", execution_id, len(config)
    )
    return tmp_path


def cleanup_config(execution_id: str) -> None:
    """
    Securely delete the temp config file for a finished execution.

    Safe to call multiple times — logs a warning if the file is already gone
    but does not raise. Should be called in a finally block so it always runs,
    even on crashes.
    """
    tmp_path = settings.data_dir / "tmp" / f"run_{execution_id}.json"
    try:
        tmp_path.unlink()
        logger.debug("Config cleaned up for execution %s", execution_id)
    except FileNotFoundError:
        logger.warning(
            "Config file already gone for execution %s (double-cleanup?)", execution_id
        )
    except OSError as exc:
        logger.error(
            "Failed to delete config for execution %s: %s", execution_id, exc
        )
