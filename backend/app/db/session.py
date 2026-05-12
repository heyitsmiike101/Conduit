"""
Database session management for Conduit.

Provides:
  - engine       — SQLAlchemy engine (SQLite with thread-safety disabled for async use)
  - SessionLocal — session factory, used directly in tests and scripts
  - get_db()     — FastAPI dependency that yields a session and closes it on exit
  - init_db()    — creates all tables on first run (idempotent)

For future migration to Alembic:
  Replace init_db() with `alembic upgrade head` in the startup sequence.
  SessionLocal and get_db() stay the same.
"""

import logging
import time

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_is_sqlite = settings.database_url.startswith("sqlite")

# check_same_thread=False: required for SQLite with FastAPI's async handling.
# timeout=30: Python-level retry when sqlite3.connect() itself is blocked.
_connect_args = {"check_same_thread": False, "timeout": 30} if _is_sqlite else {}

# SQLite is single-writer; use a pool of exactly one connection so all
# operations in this process share it and never compete for file-level locks.
# pool_size=1 / max_overflow=0 means a second caller waits (pool_timeout=30s)
# rather than opening a second connection that would race for the lock.
_pool_kwargs = {"pool_size": 1, "max_overflow": 0, "pool_timeout": 30} if _is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=(settings.log_level.upper() == "DEBUG"),
    **_pool_kwargs,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Avoid lazy-load errors after commit in async contexts
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db():
    """
    Yield a database session for a single request, then close it.

    Usage in a route:
        from fastapi import Depends
        from app.db import get_db

        @router.get("/things")
        def list_things(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Startup helper
# ---------------------------------------------------------------------------


def _run_migrations(conn) -> None:
    """
    Apply lightweight additive migrations for columns that were added after
    the initial create_all. Each migration is idempotent — safe to run every
    startup. Only needed until Alembic is introduced (deferred to future iter).
    """
    inspector = inspect(conn)

    # ── variables.variable_type (added Iteration 2 patch) ─────────────────
    existing_cols = {c["name"] for c in inspector.get_columns("variables")}
    if "variable_type" not in existing_cols:
        conn.execute(text("ALTER TABLE variables ADD COLUMN variable_type VARCHAR(50) NOT NULL DEFAULT 'config'"))
        logger.info("Migration: added variables.variable_type column")

    if "updated_at" not in existing_cols:
        conn.execute(text("ALTER TABLE variables ADD COLUMN updated_at DATETIME"))
        logger.info("Migration: added variables.updated_at column")

    # ── scripts.selected_variable_ids ─────────────────────────────────────
    script_cols = {c["name"] for c in inspector.get_columns("scripts")}
    if "selected_variable_ids" not in script_cols:
        conn.execute(text("ALTER TABLE scripts ADD COLUMN selected_variable_ids TEXT"))
        logger.info("Migration: added scripts.selected_variable_ids column")

    # ── script_versions.file_path ──────────────────────────────────────────
    if inspector.has_table("script_versions"):
        version_cols = {c["name"] for c in inspector.get_columns("script_versions")}
        if "file_path" not in version_cols:
            conn.execute(text("ALTER TABLE script_versions ADD COLUMN file_path VARCHAR(500)"))
            logger.info("Migration: added script_versions.file_path column")


def init_db(retries: int = 8, delay: float = 2.0) -> None:
    """
    Create all tables defined in models.py if they do not already exist.

    This is idempotent — safe to call on every startup. Does not drop or
    modify existing tables. Logs the table count on success.

    Retries on "database is locked" — can occur on Docker Desktop (Windows)
    when stale WAL/SHM files from a previous run are still being cleaned up.
    If the lock persists across all retries, re-raises the original error.
    Delete conduit.db / conduit.db-wal / conduit.db-shm to hard-reset.
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            Base.metadata.create_all(bind=engine)
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            if "database is locked" not in str(exc).lower():
                raise
            logger.warning(
                "Database locked during init (attempt %d/%d), retrying in %.0fs...",
                attempt + 1, retries, delay,
            )
            time.sleep(delay)

    if last_exc is not None:
        raise RuntimeError(
            "Database still locked after all retries. "
            "Delete conduit.db / conduit.db-wal / conduit.db-shm in your data directory and restart."
        ) from last_exc

    # Run additive column migrations (idempotent)
    with engine.begin() as conn:
        _run_migrations(conn)

    # Count tables to confirm creation
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    logger.info(
        "Database initialized — %d tables ready: %s",
        len(table_names),
        ", ".join(sorted(table_names)),
    )
