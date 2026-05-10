"""
Accounts API — CRUD for tenant accounts.

Routes:
  GET    /accounts          — list all accounts
  POST   /accounts          — create account
  GET    /accounts/{id}     — get one account
  DELETE /accounts/{id}     — delete account (cascades to scripts/variables/tables)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Account
from app.schemas.accounts import AccountCreate, AccountResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountResponse])
def list_accounts(db: Session = Depends(get_db)) -> list[Account]:
    """Return all accounts ordered by name."""
    return db.query(Account).order_by(Account.name).all()


@router.post("", response_model=AccountResponse, status_code=201)
def create_account(body: AccountCreate, db: Session = Depends(get_db)) -> Account:
    """Create a new tenant account."""
    existing = db.query(Account).filter_by(name=body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Account '{body.name}' already exists")

    account = Account(name=body.name)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: str, db: Session = Depends(get_db)) -> Account:
    """Return a single account by ID."""
    account = db.query(Account).filter_by(id=account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")
    return account


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: str, db: Session = Depends(get_db)) -> None:
    """Delete an account and all its associated data (cascade)."""
    account = db.query(Account).filter_by(id=account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")
    db.delete(account)
    db.commit()
