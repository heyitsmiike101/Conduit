"""
Logging configuration for the Conduit backend.

Call configure_logging() once at application startup (inside the lifespan
context manager in main.py). After that, every module can use the standard
logging.getLogger(__name__) pattern — no further setup needed.

Log format:  2026-05-07 14:23:01,123 INFO app.services.runner: Starting script abc123
"""

import logging

from app.core.config import settings

# Third-party loggers that are too chatty at their default level.
# These are suppressed to WARNING regardless of the app's own log level.
_NOISY_LOGGERS = [
    "apscheduler",
    "apscheduler.executors.default",
    "apscheduler.scheduler",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "urllib3",
    "httpx",
    "httpcore",
]

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    """
    Configure the root logger for the Conduit application.

    Sets the log level from settings.log_level (default: INFO) and applies
    a consistent timestamp format. Noisy third-party loggers are capped at
    WARNING so they don't pollute the output during normal operation.

    This function is idempotent — calling it multiple times is safe.
    """
    level = logging.getLevelName(settings.log_level.upper())
    if not isinstance(level, int):
        # getLevelName returns a string like "Level 25" for unknown names
        logging.warning(
            "Unknown log level %r — defaulting to INFO", settings.log_level
        )
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
        force=True,  # Override any existing handlers (e.g. uvicorn's defaults)
    )

    # Suppress noisy third-party loggers
    for logger_name in _NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    logging.getLogger("app").info(
        "Logging configured — level=%s", settings.log_level.upper()
    )
