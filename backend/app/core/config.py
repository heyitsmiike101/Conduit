"""
Application configuration.

All settings can be overridden via environment variables or a .env file.
Pydantic-settings automatically reads from both sources.
"""

from pathlib import Path
from typing import Any

from pydantic import ConfigDict, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the repo root once — config.py is at backend/app/core/config.py,
# so parents[3] is the repo root (Conduit/).
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """
    Central configuration for the Conduit platform.

    Environment variable names match field names exactly (case-insensitive).
    List fields (like cors_allowed_origins) can be set as comma-separated
    strings in the environment: CORS_ALLOWED_ORIGINS="http://localhost:5173,http://localhost:3000"

    frozen=False allows the PATCH /settings endpoint to mutate fields at runtime
    so changes take effect without a server restart. A settings_override.json file
    in data_dir persists those changes across restarts.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        frozen=False,   # allow runtime mutation via PATCH /settings
    )

    # --- Paths ---
    data_dir: Path = _REPO_ROOT / "data"
    secret_key_path: Path = _REPO_ROOT / "data" / ".secret_key"

    # --- Database ---
    database_url: str = f"sqlite:///{_REPO_ROOT / 'data' / 'conduit.db'}"

    # --- Concurrency ---
    max_concurrent_scripts: int = 10

    # --- Metrics ---
    metrics_interval_seconds: int = 30
    warn_threshold: float = 0.75
    critical_threshold: float = 0.90

    # --- CORS ---
    # In .env, set as a comma-separated string:
    #   CORS_ALLOWED_ORIGINS="http://localhost:5173,https://myapp.com"
    cors_allowed_origins: list[str] = ["*"]

    # --- Logging ---
    log_level: str = "INFO"

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Allow comma-separated string from environment variables."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("max_concurrent_scripts", mode="after")
    @classmethod
    def validate_concurrency(cls, value: int) -> int:
        """Concurrency limit must be at least 1."""
        if value < 1:
            raise ValueError("max_concurrent_scripts must be >= 1")
        return value

    @field_validator("data_dir", "secret_key_path", mode="after")
    @classmethod
    def resolve_paths(cls, value: Path) -> Path:
        """Ensure all paths are absolute."""
        return value.resolve()


# Exported singleton — import this everywhere
settings = Settings()
