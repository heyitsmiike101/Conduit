"""
Tables API — CRUD for InfoTable and InfoTableRow.

Routes:
  GET    /tables                      — list tables
  POST   /tables                      — create table
  GET    /tables/{id}                 — get table
  DELETE /tables/{id}                 — delete table (and all rows)
  GET    /tables/{id}/rows            — list rows
  POST   /tables/{id}/rows            — insert row
  PATCH  /tables/{id}/rows/{row_id}   — update row
  DELETE /tables/{id}/rows/{row_id}   — delete row

All admin/UI access bypasses script permission checks (script_id=None).
"""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import InfoTable
from app.schemas.tables import (
    InfoTableCreate,
    InfoTableResponse,
    InfoTableRowCreate,
    InfoTableRowResponse,
)
from app.services.tables_service import (
    create_table,
    delete_row,
    delete_table,
    get_rows,
    get_table,
    insert_row,
    list_tables,
    update_row,
)

router = APIRouter(prefix="/tables", tags=["tables"])


# ---------------------------------------------------------------------------
# Table CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[InfoTableResponse])
def list_tables_route(
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[InfoTable]:
    """List all tables. Optional ?account_id= filter."""
    return list_tables(scope=None, account_id=account_id, db=db)


@router.post("", response_model=InfoTableResponse, status_code=201)
def create_table_route(body: InfoTableCreate, db: Session = Depends(get_db)) -> InfoTable:
    """Create a new table with the given schema."""
    try:
        schema = json.loads(body.schema_json)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid schema JSON: {exc}") from exc

    return create_table(
        name=body.name,
        scope=body.scope,
        account_id=body.account_id,
        schema=schema,
        db=db,
    )


@router.get("/{table_id}", response_model=InfoTableResponse)
def get_table_route(table_id: str, db: Session = Depends(get_db)) -> InfoTable:
    """Return a table by ID."""
    try:
        return get_table(table_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{table_id}", response_model=InfoTableResponse)
def patch_table_route(
    table_id: str,
    body: dict,
    db: Session = Depends(get_db),
) -> InfoTable:
    """Update table metadata — currently supports updating schema_json."""
    try:
        tbl = get_table(table_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if "schema_json" in body:
        try:
            json.loads(body["schema_json"])  # validate JSON
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid schema JSON: {exc}") from exc
        tbl.schema_json = body["schema_json"]

    db.commit()
    db.refresh(tbl)
    return tbl


@router.delete("/{table_id}", status_code=204)
def delete_table_route(table_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a table and all its rows."""
    try:
        delete_table(table_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Row CRUD
# ---------------------------------------------------------------------------


@router.get("/{table_id}/rows", response_model=list[InfoTableRowResponse])
def list_rows(table_id: str, db: Session = Depends(get_db)) -> list:
    """Return all rows for a table, ordered by creation time."""
    try:
        return get_rows(table_id, db, script_id=None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{table_id}/rows", response_model=InfoTableRowResponse, status_code=201)
def insert_row_route(
    table_id: str,
    body: InfoTableRowCreate,
    db: Session = Depends(get_db),
) -> object:
    """Insert a row into a table."""
    try:
        return insert_row(table_id, body.row_data, db, script_id=None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{table_id}/rows/{row_id}", response_model=InfoTableRowResponse)
def update_row_route(
    table_id: str,
    row_id: str,
    body: InfoTableRowCreate,
    db: Session = Depends(get_db),
) -> object:
    """Update a row's data."""
    # Verify the row belongs to this table
    try:
        get_table(table_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        return update_row(row_id, body.row_data, db, script_id=None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{table_id}/rows/{row_id}", status_code=204)
def delete_row_route(
    table_id: str,
    row_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete a single row."""
    try:
        get_table(table_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        delete_row(row_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
