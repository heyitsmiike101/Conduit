"""
Tables service — CRUD for InfoTable and InfoTableRow.

Permission enforcement: when a script accesses a table, its ScriptPermission
row is checked. A missing permission row is treated as deny-all (defensive default).
Direct UI/admin access bypasses permission checks (pass script_id=None).
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.db.models import InfoTable, InfoTableRow, ScriptPermission, ScriptScope

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Table CRUD
# ---------------------------------------------------------------------------


def create_table(
    name: str,
    scope: ScriptScope,
    account_id: Optional[str],
    schema: Dict[str, Any],
    db: Session,
) -> InfoTable:
    """Create a new InfoTable with the given schema."""
    table = InfoTable(
        name=name,
        scope=scope,
        account_id=account_id,
        schema_json=json.dumps(schema),
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    logger.info("Created table '%s' (id=%s, scope=%s)", name, table.id, scope.value)
    return table


def get_table(table_id: str, db: Session) -> InfoTable:
    """
    Fetch a table by ID.

    Raises:
        ValueError: If the table does not exist.
    """
    table = db.query(InfoTable).filter_by(id=table_id).first()
    if not table:
        raise ValueError(f"Table '{table_id}' not found")
    return table


def list_tables(
    scope: Optional[ScriptScope],
    account_id: Optional[str],
    db: Session,
) -> List[InfoTable]:
    """List tables, optionally filtered by scope and/or account."""
    query = db.query(InfoTable)
    if scope is not None:
        query = query.filter(InfoTable.scope == scope)
    if account_id is not None:
        query = query.filter(InfoTable.account_id == account_id)
    return query.order_by(InfoTable.name).all()


def delete_table(table_id: str, db: Session) -> None:
    """
    Delete a table and all its rows (cascade handled by ORM).

    Raises:
        ValueError: If the table does not exist.
    """
    table = get_table(table_id, db)
    db.delete(table)
    db.commit()
    logger.info("Deleted table '%s'", table_id)


# ---------------------------------------------------------------------------
# Row CRUD
# ---------------------------------------------------------------------------


def _check_write_permission(script_id: str, db: Session) -> None:
    """
    Verify a script has write permission on tables.

    A missing ScriptPermission row is treated as deny-all.

    Raises:
        PermissionError: If the script lacks write permission.
    """
    perm = db.query(ScriptPermission).filter_by(script_id=script_id).first()
    if not perm or not perm.can_write_tables:
        raise PermissionError(
            f"Script '{script_id}' does not have write permission on tables. "
            "Grant it via the script's permissions settings."
        )


def _check_read_permission(script_id: str, db: Session) -> None:
    """
    Verify a script has read permission on tables.

    Raises:
        PermissionError: If the script lacks read permission.
    """
    perm = db.query(ScriptPermission).filter_by(script_id=script_id).first()
    if not perm or not perm.can_read_tables:
        raise PermissionError(
            f"Script '{script_id}' does not have read permission on tables."
        )


def insert_row(
    table_id: str,
    row_data: Dict[str, Any],
    db: Session,
    script_id: Optional[str] = None,
) -> InfoTableRow:
    """
    Insert a row into a table.

    Args:
        table_id: Target table ID.
        row_data: Arbitrary key-value dict for the row.
        db: SQLAlchemy session.
        script_id: If provided, the caller's script ID — permission is enforced.
                   Pass None for admin/UI access (no permission check).

    Raises:
        ValueError: If the table does not exist.
        PermissionError: If script_id is provided but lacks write permission.
    """
    # Verify table exists
    get_table(table_id, db)

    # Enforce permissions when called from a script
    if script_id is not None:
        _check_write_permission(script_id, db)

    row = InfoTableRow(
        table_id=table_id,
        row_data_json=json.dumps(row_data),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_rows(
    table_id: str,
    db: Session,
    script_id: Optional[str] = None,
) -> List[InfoTableRow]:
    """
    Return all rows for a table.

    Args:
        script_id: If provided, read permission is enforced.
    """
    get_table(table_id, db)  # Verify table exists

    if script_id is not None:
        _check_read_permission(script_id, db)

    return (
        db.query(InfoTableRow)
        .filter_by(table_id=table_id)
        .order_by(InfoTableRow.created_at)
        .all()
    )


def update_row(
    row_id: str,
    row_data: Dict[str, Any],
    db: Session,
    script_id: Optional[str] = None,
) -> InfoTableRow:
    """
    Update a row's data.

    Raises:
        ValueError: If the row does not exist.
        PermissionError: If script_id is provided but lacks write permission.
    """
    row = db.query(InfoTableRow).filter_by(id=row_id).first()
    if not row:
        raise ValueError(f"Row '{row_id}' not found")

    if script_id is not None:
        _check_write_permission(script_id, db)

    row.row_data_json = json.dumps(row_data)
    db.commit()
    db.refresh(row)
    return row


def delete_row(row_id: str, db: Session) -> None:
    """
    Delete a single row.

    Raises:
        ValueError: If the row does not exist.
    """
    row = db.query(InfoTableRow).filter_by(id=row_id).first()
    if not row:
        raise ValueError(f"Row '{row_id}' not found")
    db.delete(row)
    db.commit()
