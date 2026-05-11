"""
SQLAlchemy ORM models for Conduit.

All 13 tables are defined here. Enums are Python enum classes so they can be
imported and used throughout the codebase without magic strings.

Design notes:
  - UUIDs stored as String(36) — simple, portable, readable in SQLite browser
  - All timestamps are UTC. No timezone info stored — callers assume UTC.
  - Cascade deletes are handled at the ORM level (cascade="all, delete-orphan")
    so deleting a parent removes its children cleanly via SQLAlchemy.
  - users / sessions tables exist but are intentionally unused until login
    is implemented (future iteration).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ScriptScope(str, enum.Enum):
    """Whether a script or variable belongs to all accounts or one specific account."""
    GLOBAL = "global"
    ACCOUNT = "account"


class ExecutionStatus(str, enum.Enum):
    """Lifecycle states for a single script run."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"


class LogStream(str, enum.Enum):
    """Source stream of an execution log entry."""
    STDOUT = "stdout"
    STDERR = "stderr"
    API = "api"  # Calls logged via conduit-helper log_api_call()


class NotificationLevel(str, enum.Enum):
    """Severity of a platform notification."""
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def _now() -> datetime:
    """Return current UTC time."""
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Account(Base):
    """
    A tenant of the platform. Scripts, variables, and tables are scoped
    to either 'global' (shared across all accounts) or a specific account.
    """

    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # Relationships — cascade so deleting an account cleans up its data
    scripts: Mapped[List[Script]] = relationship(
        "Script", back_populates="account", cascade="all, delete-orphan"
    )
    variables: Mapped[List[Variable]] = relationship(
        "Variable", back_populates="account", cascade="all, delete-orphan"
    )
    info_tables: Mapped[List[InfoTable]] = relationship(
        "InfoTable", back_populates="account", cascade="all, delete-orphan"
    )


class Script(Base):
    """
    A Python script managed by the platform. The actual code lives on disk
    at file_path. The DB row is the canonical source of metadata.
    """

    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scope: Mapped[ScriptScope] = mapped_column(SAEnum(ScriptScope), nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    selected_variable_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    script_type: Mapped[str] = mapped_column(String(50), default="script", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    # Relationships
    account: Mapped[Optional[Account]] = relationship("Account", back_populates="scripts")
    permission: Mapped[Optional[ScriptPermission]] = relationship(
        "ScriptPermission",
        back_populates="script",
        cascade="all, delete-orphan",
        uselist=False,
    )
    cron_jobs: Mapped[List[CronJob]] = relationship(
        "CronJob", back_populates="script", cascade="all, delete-orphan"
    )
    executions: Mapped[List[Execution]] = relationship(
        "Execution", back_populates="script", cascade="all, delete-orphan"
    )
    versions: Mapped[List["ScriptVersion"]] = relationship(
        "ScriptVersion", back_populates="script", cascade="all, delete-orphan"
    )


class ScriptPermission(Base):
    """
    Table-access permissions for a script. Created automatically (all False)
    when a script is created. A missing row is treated as deny-all.
    """

    __tablename__ = "script_permissions"

    script_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scripts.id", ondelete="CASCADE"), primary_key=True
    )
    can_read_tables: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_write_tables: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_create_tables: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    script: Mapped[Script] = relationship("Script", back_populates="permission")


class CronJob(Base):
    """A scheduled trigger for a script. Stored in APScheduler and here."""

    __tablename__ = "cron_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cron_expression: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    script: Mapped[Script] = relationship("Script", back_populates="cron_jobs")


class Execution(Base):
    """
    A single run of a script. Created when a run is triggered (cron or manual).
    History is retained forever — never auto-deleted.
    """

    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    return_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus), default=ExecutionStatus.QUEUED, nullable=False
    )

    script: Mapped[Script] = relationship("Script", back_populates="executions")
    logs: Mapped[List[ExecutionLog]] = relationship(
        "ExecutionLog", back_populates="execution", cascade="all, delete-orphan"
    )


class ExecutionLog(Base):
    """
    A single line (or chunk) of output from a script execution.
    Uses an auto-increment integer PK for insertion speed.
    """

    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stream: Mapped[LogStream] = mapped_column(SAEnum(LogStream), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now)

    execution: Mapped[Execution] = relationship("Execution", back_populates="logs")


class Variable(Base):
    """
    A named value available to scripts at runtime. Secrets are encrypted
    at rest via Fernet and never written to logs.

    variable_type:
      "config"  — regular config value, optionally secret/revealable
      "api_key" — always masked, never revealable after creation
    """

    __tablename__ = "variables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scope: Mapped[ScriptScope] = mapped_column(SAEnum(ScriptScope), nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    variable_type: Mapped[str] = mapped_column(String(50), default="config", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    account: Mapped[Optional[Account]] = relationship("Account", back_populates="variables")


class InfoTable(Base):
    """
    A structured data table scripts can read from and write to.
    Schema is stored as JSON — columns are defined there, not in SQL.
    """

    __tablename__ = "info_tables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scope: Mapped[ScriptScope] = mapped_column(SAEnum(ScriptScope), nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    account: Mapped[Optional[Account]] = relationship("Account", back_populates="info_tables")
    rows: Mapped[List[InfoTableRow]] = relationship(
        "InfoTableRow", back_populates="table", cascade="all, delete-orphan"
    )


class InfoTableRow(Base):
    """A single row in an InfoTable. Row data is stored as a JSON blob."""

    __tablename__ = "info_table_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    table_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("info_tables.id", ondelete="CASCADE"), nullable=False
    )
    row_data_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    table: Mapped[InfoTable] = relationship("InfoTable", back_populates="rows")


class Notification(Base):
    """
    Platform notification. Never auto-resolved — requires manual dismissal.
    Used for system health alerts and missing-file warnings.
    """

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    level: Mapped[NotificationLevel] = mapped_column(
        SAEnum(NotificationLevel), nullable=False
    )
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class SystemMetric(Base):
    """
    A single sampled metric value. Collected every 30 seconds.
    Rows older than 30 days are pruned by metrics_service.
    Uses auto-increment PK for fast sequential inserts.
    """

    __tablename__ = "system_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class ScriptVersion(Base):
    """
    Immutable snapshot of a script's code at a point in time.
    Created automatically each time a script's content is saved via the UI.
    Allows rolling back to any prior version.
    """

    __tablename__ = "script_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    script: Mapped[Script] = relationship("Script", back_populates="versions")


class User(Base):
    """
    Platform administrator account. Table exists from day one to avoid
    painful migrations later — unused until login is implemented.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(1024), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sessions: Mapped[List[Session]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    """
    Authentication session. Unused until login is implemented.
    Paired with User — see security.py for the future implementation plan.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="sessions")


class AuditLog(Base):
    """
    Immutable audit trail for sensitive platform operations.

    Records who did what, when, and to which resource. User is nullable
    so unauthenticated actions (e.g. before auth is enabled) are still tracked.
    Never delete rows — append-only table.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Nullable — logs pre-auth operations or system-initiated actions.
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Denormalised so deleting a user doesn't lose audit history
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # e.g. "script.create", "variable.delete", "auth.login"
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # e.g. "script", "variable", "cron_job"
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    resource_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Human-readable name at time of action
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
