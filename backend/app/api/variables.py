"""
Variables API — CRUD for encrypted configuration variables.

Routes:
  GET    /variables                  — list variables (never returns raw secret values)
  POST   /variables                  — create variable (value encrypted at rest)
  GET    /variables/{id}             — get one variable
  GET    /variables/{id}/value       — reveal plaintext value (secrets returned as "***" unless ?reveal=true)
  PATCH  /variables/{id}             — update variable
  DELETE /variables/{id}             — delete variable
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Variable
from app.schemas.variables import VariableCreate, VariableResponse, VariableUpdate, VariableValueResponse
from app.services.encryption_service import get_variable_value
from app.core.encryption import encryption_service

# Note: list/get routes return ORM Variable objects directly.
# VariableResponse.decrypt_value() model_validator handles ORM → schema conversion,
# decrypting value_encrypted and masking secrets automatically.

router = APIRouter(prefix="/variables", tags=["variables"])


@router.get("", response_model=list[VariableResponse])
def list_variables(
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[Variable]:
    """
    Return all variables.

    Secret values are masked as "***" in VariableResponse.
    Optional ?account_id= to filter by tenant.
    """
    query = db.query(Variable)
    if account_id is not None:
        query = query.filter(Variable.account_id == account_id)
    return query.order_by(Variable.name).all()


@router.post("", response_model=VariableResponse, status_code=201)
def create_variable(body: VariableCreate, db: Session = Depends(get_db)) -> Variable:
    """Create a variable. Value is encrypted before storage."""
    variable = Variable(
        scope=body.scope,
        account_id=body.account_id,
        name=body.name,
        value_encrypted=encryption_service.encrypt(body.value),
        is_secret=body.is_secret,
        variable_type=body.variable_type,
    )
    db.add(variable)
    db.commit()
    db.refresh(variable)
    return variable


@router.get("/{variable_id}", response_model=VariableResponse)
def get_variable(variable_id: str, db: Session = Depends(get_db)) -> Variable:
    """Return a variable by ID (secret values masked)."""
    variable = db.query(Variable).filter_by(id=variable_id).first()
    if not variable:
        raise HTTPException(status_code=404, detail=f"Variable '{variable_id}' not found")
    return variable


@router.get("/{variable_id}/value", response_model=VariableValueResponse)
def get_variable_value_route(
    variable_id: str,
    reveal: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """
    Return the plaintext value of a variable.

    Secret variables return "***" unless ?reveal=true is passed.
    Use this endpoint sparingly — the plain value is sensitive.
    """
    variable = db.query(Variable).filter_by(id=variable_id).first()
    if not variable:
        raise HTTPException(status_code=404, detail=f"Variable '{variable_id}' not found")

    return {
        "id": variable.id,
        "name": variable.name,
        "value": get_variable_value(variable, reveal_secret=reveal),
        "is_secret": variable.is_secret,
    }


@router.patch("/{variable_id}", response_model=VariableResponse)
def update_variable(
    variable_id: str,
    body: VariableUpdate,
    db: Session = Depends(get_db),
) -> Variable:
    """Update a variable. If value is provided, it is re-encrypted."""
    variable = db.query(Variable).filter_by(id=variable_id).first()
    if not variable:
        raise HTTPException(status_code=404, detail=f"Variable '{variable_id}' not found")

    update_data = body.model_dump(exclude_unset=True)

    # Encrypt the new value if provided
    if "value" in update_data:
        variable.value_encrypted = encryption_service.encrypt(update_data.pop("value"))

    for field, value in update_data.items():
        setattr(variable, field, value)

    db.commit()
    db.refresh(variable)
    return variable


@router.delete("/{variable_id}", status_code=204)
def delete_variable(variable_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a variable."""
    variable = db.query(Variable).filter_by(id=variable_id).first()
    if not variable:
        raise HTTPException(status_code=404, detail=f"Variable '{variable_id}' not found")
    db.delete(variable)
    db.commit()
