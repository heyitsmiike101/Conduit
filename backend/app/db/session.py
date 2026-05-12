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
# timeout=30: wait up to 30s for a lock instead of failing immediately — needed
# in Docker where a restarting container may briefly overlap with the previous
# one still holding a write lock during shutdown.
_connect_args = {"check_same_thread": False, "timeout": 30} if _is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    # Only echo SQL when log level is DEBUG. configure_logging() also suppresses
    # the sqlalchemy.engine logger to WARNING in non-debug mode as a safety net,
    # but avoiding echo=True is cleaner and avoids the overhead entirely.
    echo=(settings.log_level.upper() == "DEBUG"),
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        # WAL mode: allows concurrent reads alongside a single writer, and
        # survives crashes without requiring a full journal rollback on next open.
        cursor.execute("PRAGMA journal_mode=WAL")
        # busy_timeout: SQLite-level retry duration (ms) when another connection
        # holds a write lock — complements the Python-level timeout above.
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


def init_db() -> None:
    """
    Create all tables defined in models.py if they do not already exist.

    This is idempotent — safe to call on every startup. Does not drop or
    modify existing tables. Logs the table count on success.

    For production environments that need migrations, replace this with
    Alembic (deferred to a future iteration).
    """
    Base.metadata.create_all(bind=engine)

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
