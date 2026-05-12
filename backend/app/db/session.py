"""
Database session management for Conduit.

Provides:
  - engine       — SQLAlchemy engine
  - SessionLocal — session factory
  - get_db()     — FastAPI dependency that yields a session per request
  - init_db()    — creates all tables on first run (idempotent)
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

# SQLite only: disable same-thread check (FastAPI uses multiple threads)
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=(settings.log_level.upper() == "DEBUG"),
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Startup helper
# ---------------------------------------------------------------------------

# TIMESTAMP is the correct type for PostgreSQL; SQLite accepts DATETIME.
_ts_type = "DATETIME" if _is_sqlite else "TIMESTAMP"


def _run_migrations(conn) -> None:
    """
    Additive column migrations applied on every startup (idempotent).
    Each block checks whether the column exists before altering the table.
    """
    inspector = inspect(conn)

    var_cols = {c["name"] for c in inspector.get_columns("variables")}
    if "variable_type" not in var_cols:
        conn.execute(text("ALTER TABLE variables ADD COLUMN variable_type VARCHAR(50) NOT NULL DEFAULT 'config'"))
        logger.info("Migration: added variables.variable_type")
    if "updated_at" not in var_cols:
        conn.execute(text(f"ALTER TABLE variables ADD COLUMN updated_at {_ts_type}"))
        logger.info("Migration: added variables.updated_at")

    script_cols = {c["name"] for c in inspector.get_columns("scripts")}
    if "selected_variable_ids" not in script_cols:
        conn.execute(text("ALTER TABLE scripts ADD COLUMN selected_variable_ids TEXT"))
        logger.info("Migration: added scripts.selected_variable_ids")

    if inspector.has_table("script_versions"):
        ver_cols = {c["name"] for c in inspector.get_columns("script_versions")}
        if "file_path" not in ver_cols:
            conn.execute(text("ALTER TABLE script_versions ADD COLUMN file_path VARCHAR(500)"))
            logger.info("Migration: added script_versions.file_path")


def init_db() -> None:
    """
    Create all tables if they don't exist, then run additive column migrations.
    Idempotent — safe to call on every startup.
    """
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        _run_migrations(conn)

    table_names = inspect(engine).get_table_names()
    logger.info(
        "Database initialized — %d tables: %s",
        len(table_names),
        ", ".join(sorted(table_names)),
    )
