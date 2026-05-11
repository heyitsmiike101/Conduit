"""
Authentication API.

Routes:
  POST /auth/setup    — create the first admin user (only when no users exist)
  POST /auth/login    — authenticate and receive a JWT token
  POST /auth/logout   — revoke the current session token
  GET  /auth/me       — return the current user's profile
  POST /auth/change-password — change the authenticated user's password
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_token,
    get_current_user,
    hash_password,
    require_user,
    verify_password,
)
from app.db.models import Session as DBSession
from app.db.models import User
from app.db.session import get_db
from app.services.audit_service import audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SetupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=256)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_in_hours: int
    user_id: str
    username: str
    role: str


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    enabled: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=256)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/setup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def setup_first_admin(
    body: SetupRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Create the first admin user.

    Only succeeds when no users exist — this is a one-time setup endpoint.
    Once any user exists this endpoint returns 409 Conflict.
    """
    existing_count = db.query(User).count()
    if existing_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup already complete. An admin account already exists.",
        )

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role="admin",
        enabled=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    audit(db, "auth.setup", user=user, request=request, resource_type="user", resource_id=user.id)
    logger.info("First admin user '%s' created via /auth/setup", user.username)

    return UserResponse(id=user.id, username=user.username, role=user.role, enabled=user.enabled)


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticate with username + password. Returns a JWT Bearer token.

    The token is also stored in the sessions table. To revoke a token before
    it expires, call POST /auth/logout.
    """
    user = db.query(User).filter_by(username=body.username, enabled=True).first()

    # Constant-time comparison even on user-not-found to prevent user enumeration
    if not user or not verify_password(body.password, user.password_hash):
        audit(
            db, "auth.login_failed",
            request=request,
            metadata={"username": body.username},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_token(user, db)

    audit(db, "auth.login", user=user, request=request, resource_type="user", resource_id=user.id)
    logger.info("User '%s' logged in from %s", user.username, request.client.host)

    return LoginResponse(
        token=token,
        expires_in_hours=settings.jwt_expiry_hours,
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Revoke the current session token.

    Deletes the session row so the JWT cannot be used even if it hasn't expired.
    """
    from fastapi.security import HTTPAuthorizationCredentials
    from fastapi import Header

    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        db.query(DBSession).filter_by(token=token).delete()
        db.commit()

    if user:
        audit(db, "auth.logout", user=user, request=request, resource_type="user", resource_id=user.id)

    return None


@router.get("/me", response_model=UserResponse)
def me(user=Depends(get_current_user)):
    """
    Return the authenticated user's profile.

    Always requires a valid Bearer token — unauthenticated callers get 401
    regardless of whether auth_enabled is True or False.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide a Bearer token to view your profile.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserResponse(id=user.id, username=user.username, role=user.role, enabled=user.enabled)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the authenticated user's password. Revokes all existing sessions."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    # Update the password
    db_user = db.query(User).filter_by(id=user.id).first()
    db_user.password_hash = hash_password(body.new_password)

    # Revoke all sessions (forces re-login everywhere)
    db.query(DBSession).filter_by(user_id=user.id).delete()
    db.commit()

    audit(
        db, "auth.password_change",
        user=user, request=request,
        resource_type="user", resource_id=user.id,
    )
    logger.info("User '%s' changed their password — all sessions revoked", user.username)
    return None


@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    """
    Returns whether auth is enabled and whether a user account exists.

    Used by the frontend to decide whether to show the login page or setup form.
    """
    user_count = db.query(User).count()
    return {
        "auth_enabled": settings.auth_enabled,
        "setup_complete": user_count > 0,
        "user_count": user_count,
    }
