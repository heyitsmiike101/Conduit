"""
Config loader for Conduit-managed scripts.

Two modes:

  Production mode (default — running inside Conduit runner):
    - Reads config from the file path in --conduit-config=<path> CLI arg
    - Reads execution ID from --conduit-execution-id=<id> CLI arg
    - Logs API calls via HTTP to the internal platform endpoint

  Dev mode (CONDUIT_DEV_MODE=1 environment variable):
    - Reads config from ./conduit_fixtures/config.json (relative to CWD)
    - Execution ID is set to "dev-mode" (log_api_call prints to stdout)
    - No connection to the backend needed — works fully offline
    - Ideal for local development and testing

Usage:
    from conduit import get_config
    config = get_config()
    api_key = config["API_KEY"]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

# Cached config — loaded once on first call
_config: Optional[Dict[str, str]] = None
_execution_id: Optional[str] = None
_api_base: Optional[str] = None
_dev_mode: Optional[bool] = None


def is_dev_mode() -> bool:
    """Return True if CONDUIT_DEV_MODE=1 is set in the environment."""
    global _dev_mode
    if _dev_mode is None:
        _dev_mode = os.environ.get("CONDUIT_DEV_MODE", "").strip() in ("1", "true", "yes")
    return _dev_mode


def _parse_conduit_args() -> tuple:
    """
    Extract --conduit-config and --conduit-execution-id from sys.argv.

    Returns:
        (config_path, execution_id) — either may be None if not provided.
    """
    config_path: Optional[str] = None
    execution_id: Optional[str] = None

    for arg in sys.argv[1:]:
        if arg.startswith("--conduit-config="):
            config_path = arg.split("=", 1)[1]
        elif arg.startswith("--conduit-execution-id="):
            execution_id = arg.split("=", 1)[1]

    return config_path, execution_id


def _load_dev_mode() -> None:
    """Load config from ./conduit_fixtures/config.json for local development."""
    global _config, _execution_id, _api_base

    _execution_id = "dev-mode"

    fixture_path = Path.cwd() / "conduit_fixtures" / "config.json"
    if fixture_path.exists():
        try:
            _config = json.loads(fixture_path.read_text(encoding="utf-8"))
            print(f"[conduit dev] Loaded config from {fixture_path} ({len(_config)} keys)")
        except json.JSONDecodeError as exc:
            print(f"[conduit dev] WARNING: {fixture_path} is not valid JSON: {exc}")
            _config = {}
    else:
        print(f"[conduit dev] No fixture found at {fixture_path} — using empty config")
        print(f"[conduit dev] Create {fixture_path} to supply test variables")
        _config = {}

    _api_base = os.environ.get("CONDUIT_API_BASE", "http://localhost:8000/api/v1")


def _load_production_mode() -> None:
    """Load config from the injected file in production (inside Conduit runner)."""
    global _config, _execution_id, _api_base

    config_path_str, execution_id = _parse_conduit_args()
    _execution_id = execution_id

    if config_path_str:
        config_path = Path(config_path_str)
        if not config_path.exists():
            raise FileNotFoundError(
                f"Conduit config file not found: {config_path_str}. "
                "This file is created automatically by the Conduit runner — "
                "do not delete it before the script finishes."
            )
        try:
            _config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Conduit config file is not valid JSON: {exc}") from exc
    else:
        # Running outside the Conduit runner without dev mode — use empty config
        import warnings
        warnings.warn(
            "Conduit: --conduit-config not found in sys.argv and CONDUIT_DEV_MODE is not set. "
            "Config will be empty. Set CONDUIT_DEV_MODE=1 for local development.",
            RuntimeWarning,
            stacklevel=4,
        )
        _config = {}

    # Determine API base URL:
    #   1. CONDUIT_API_BASE env var (highest priority)
    #   2. CONDUIT_API_BASE key in the config file
    #   3. Default localhost
    _api_base = (
        os.environ.get("CONDUIT_API_BASE")
        or _config.get("CONDUIT_API_BASE")
        or "http://localhost:8000/api/v1"
    )


def _load() -> None:
    """Load config from the appropriate source. Called once."""
    if is_dev_mode():
        _load_dev_mode()
    else:
        _load_production_mode()


def get_config() -> Dict[str, str]:
    """
    Return the script's configuration dictionary.

    In production mode: values are decrypted plaintext from the Conduit variable store.
    In dev mode: values are read from ./conduit_fixtures/config.json.

    The config is loaded once and cached for the lifetime of the process.

    Returns:
        Dict mapping variable names to their values.
    """
    global _config
    if _config is None:
        _load()
    return _config


def get_execution_id() -> Optional[str]:
    """
    Return the current execution ID.

    Production mode: from --conduit-execution-id CLI arg.
    Dev mode: returns "dev-mode".
    """
    if _config is None:
        _load()
    return _execution_id


def get_api_base() -> str:
    """Return the backend API base URL for internal calls."""
    if _config is None:
        _load()
    return _api_base
