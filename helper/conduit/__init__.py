"""
Conduit helper library.

Provides the four core functions available to Conduit-managed scripts:

  get_config()        — returns the script's configuration dict (decrypted variables)
  get_table(id)       — returns a TableClient for reading/writing InfoTable rows
  log_api_call()      — records an outbound HTTP call in the execution log
  run_script(id)      — trigger another Conduit script asynchronously

Example usage in a script:
    from conduit import get_config, get_table, log_api_call, run_script

    config = get_config()
    api_key = config["MY_API_KEY"]

    # Make an external call and log it
    import httpx, time
    start = time.time()
    resp = httpx.get("https://api.example.com/data", headers={"Authorization": api_key})
    log_api_call(method="GET", url=str(resp.url), status_code=resp.status_code,
                 duration_ms=(time.time() - start) * 1000)

    # Write results to a table
    table = get_table("my-results-table-id")
    table.insert_row({"status": resp.status_code, "data": resp.json()})

    # Trigger a downstream script
    run_script("processor-script-uuid")
"""

from .config import get_config
from .tables import get_table
from .logging import log_api_call
from .runner import run_script

__all__ = ["get_config", "get_table", "log_api_call", "run_script"]
__version__ = "0.1.0"
