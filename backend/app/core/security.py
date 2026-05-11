"""
Authentication and authorisation for the Conduit platform.

Design
------
- JWT bearer tokens, signed with settings.jwt_secret.
- Tokens are also written to the sessions table for revocation support.
- bcrypt password hashing (never store plaintext).
- auth_enabled flag: when False every request passes through unauthenticated
  (safe for local dev). When True all routes require a valid token.

Public surface
--------------
  hash_password(plain)            → str          bcrypt hash
  verify_password(plain, hashed)  → bool         constant-time compare
  create_token(user, db)          → str          issue JWT + write Session row
  get_current_user(request, db)   → User | None  FastAPI dependency
  require_user(user)              → User         raises 401 if auth enabled + no user
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Session as DBSession
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plaintext password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt comparison. Returns True if the password matches."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def create_token(user: User, db: Session) -> str:
    """
    Issue a JWT for the given user and persist it to the sessions table.

    Args:
        user: The authenticated User ORM object.
        db:   A live SQLAlchemy session.

    Returns:
        A signed JWT string (Bearer token).
    """
    expiry = datetime.utcnow() + timedelta(hours=settings.jwt_expiry_hours)

    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "exp": expiry,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    # Persist to sessions table for revocation support
    session_row = DBSession(
        user_id=user.id,
        token=token,
        expires_at=expiry,
    )
    db.add(session_row)
    db.commit()

    return token


def _decode_token(token: str) -> dict:
    """
    Decode and validate a JWT.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is malformed or has wrong signature.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    FastAPI dependency — resolve the authenticated user for the current request.

    Behaviour:
      - auth_enabled=False, no token: returns None (open platform, backwards-compatible).
      - auth_enabled=False, valid token: validates and returns the User (so /auth/me works).
      - auth_enabled=True, no token:  raises HTTP 401.
      - auth_enabled=True, valid token: validates and returns the User.

    Usage in route:
        @router.get("/resource")
        def get_resource(user=Depends(get_current_user)):
            ...
    """
    # When auth is disabled and no token provided, open access
    if not settings.auth_enabled and not credentials:
        return None

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Decode JWT
    try:
        payload = _decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    # Verify the session is not revoked (row still in sessions table)
    session_row = (
        db.query(DBSession)
        .filter(DBSession.token == token, DBSession.expires_at > datetime.utcnow())
        .first()
    )
    if not session_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load the user
    user = db.query(User).filter_by(id=user_id, enabled=True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_user(user: Optional[User] = Depends(get_current_user)) -> Optional[User]:
    """
    FastAPI dependency — same as get_current_user but raises 401 when
    auth is enabled and no user is present.

    Use this on routes that must be protected when auth is on:
        @router.delete("/resource/{id}")
        def delete(user=Depends(require_user)):
            ...
    """
    if settings.auth_enabled and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
