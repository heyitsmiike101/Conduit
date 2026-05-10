"""
Table access for Conduit-managed scripts.

Production mode: reads/writes via the Conduit backend API. Permissions enforced
server-side — the script must have can_read_tables / can_write_tables set.

Dev mode (CONDUIT_DEV_MODE=1): reads rows from ./conduit_fixtures/{table_id}.json
(a JSON array). Write operations (insert, update, delete) print to stdout and
are NOT persisted — so local testing is safe and repeatable.

Usage:
    from conduit import get_table
    table = get_table("my-table-id")
    rows = table.get_rows()
    row = table.insert_row({"key": "value"})
    table.update_row(row["id"], {"key": "updated"})
    table.delete_row(row["id"])
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class DevTableClient:
    """
    Read-only table client for local development.

    Reads rows from ./conduit_fixtures/{table_id}.json.
    Write operations (insert, update, delete) print what they would do but
    do not persist — making local runs safe and idempotent.
    """

    def __init__(self, table_id: str) -> None:
        self._table_id = table_id
        self._fixture_path = Path.cwd() / "conduit_fixtures" / f"{table_id}.json"
        self._rows: Optional[List[Dict[str, Any]]] = None

    def _load_fixture(self) -> List[Dict[str, Any]]:
        if self._rows is None:
            if self._fixture_path.exists():
                try:
                    data = json.loads(self._fixture_path.read_text(encoding="utf-8"))
                    if not isinstance(data, list):
                        print(f"[conduit dev] WARNING: {self._fixture_path} must contain a JSON array")
                        data = []
                    self._rows = data
                    print(f"[conduit dev] Loaded {len(self._rows)} row(s) from {self._fixture_path}")
                except json.JSONDecodeError as exc:
                    print(f"[conduit dev] WARNING: {self._fixture_path} is invalid JSON: {exc}")
                    self._rows = []
            else:
                print(f"[conduit dev] No fixture at {self._fixture_path} — table will be empty")
                print(f"[conduit dev] Create it as a JSON array to supply test rows")
                self._rows = []
        return self._rows

    def get_rows(self) -> List[Dict[str, Any]]:
        """Return all rows from the fixture file."""
        return self._load_fixture()

    def insert_row(self, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Print the insert and return a synthetic row dict (not persisted)."""
        fake_id = str(uuid.uuid4())
        print(f"[conduit dev] INSERT into {self._table_id}: {json.dumps(row_data)}")
        return {
            "id": fake_id,
            "table_id": self._table_id,
            "row_data_json": json.dumps(row_data),
            "created_at": "dev-mode",
            "updated_at": "dev-mode",
        }

    def update_row(self, row_id: str, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Print the update (not persisted)."""
        print(f"[conduit dev] UPDATE row {row_id} in {self._table_id}: {json.dumps(row_data)}")
        return {
            "id": row_id,
            "table_id": self._table_id,
            "row_data_json": json.dumps(row_data),
            "created_at": "dev-mode",
            "updated_at": "dev-mode",
        }

    def delete_row(self, row_id: str) -> None:
        """Print the delete (not persisted)."""
        print(f"[conduit dev] DELETE row {row_id} from {self._table_id}")


class TableClient:
    """
    Live table client that calls the Conduit backend API.

    All methods call the Conduit backend API. Errors from the API
    (4xx, 5xx) are raised as RuntimeError.
    """

    def __init__(self, table_id: str, execution_id: str, api_base: str) -> None:
        self._table_id = table_id
        self._execution_id = execution_id
        self._api_base = api_base
        self._headers = {"X-Execution-ID": execution_id}

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an authenticated HTTP request to the backend."""
        import httpx
        url = f"{self._api_base}{path}"
        resp = httpx.request(
            method,
            url,
            headers=self._headers,
            timeout=30.0,
            **kwargs,
        )
        if not resp.is_success:
            raise RuntimeError(
                f"Conduit API error: {method} {url} → {resp.status_code}: {resp.text}"
            )
        if resp.status_code == 204:
            return None
        return resp.json()

    def get_rows(self) -> List[Dict[str, Any]]:
        """Return all rows in this table."""
        return self._request("GET", f"/tables/{self._table_id}/rows")

    def insert_row(self, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new row into the table."""
        return self._request(
            "POST",
            f"/tables/{self._table_id}/rows",
            json={"row_data": row_data},
        )

    def update_row(self, row_id: str, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a row's data (replaces existing content)."""
        return self._request(
            "PATCH",
            f"/tables/{self._table_id}/rows/{row_id}",
            json={"row_data": row_data},
        )

    def delete_row(self, row_id: str) -> None:
        """Delete a row from the table."""
        self._request("DELETE", f"/tables/{self._table_id}/rows/{row_id}")


def get_table(table_id: str):
    """
    Return a table client for the given table ID.

    In production mode: returns a TableClient that calls the Conduit API.
    In dev mode: returns a DevTableClient that reads from fixture files.

    Args:
        table_id: ID (or name in dev mode) of the InfoTable to access.

    Returns:
        TableClient or DevTableClient instance.
    """
    from .config import get_api_base, get_execution_id, is_dev_mode
    import warnings

    if is_dev_mode():
        return DevTableClient(table_id)

    execution_id = get_execution_id()
    if not execution_id:
        warnings.warn(
            "Conduit: get_table() called outside a Conduit execution — "
            "API calls will fail without a valid execution ID.",
            RuntimeWarning,
            stacklevel=2,
        )
        execution_id = "unknown"

    return TableClient(
        table_id=table_id,
        execution_id=execution_id,
        api_base=get_api_base(),
    )
