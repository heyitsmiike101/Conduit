"""
Example 04 — Writing to InfoTables

Demonstrates inserting and updating rows in a Conduit InfoTable.

Prerequisites in the Conduit UI:
  1. Create an InfoTable (e.g. named "run_log")
  2. Enable both can_read_tables and can_write_tables permissions for this script
  3. Set the TABLE_ID variable to the table's ID

This example:
  - Inserts a "run started" row with a timestamp
  - Does some work
  - Updates the row with the result
"""

import json
from datetime import datetime, timezone
from conduit import get_config, get_table

config = get_config()

table_id = config.get("TABLE_ID")
if not table_id:
    raise RuntimeError("TABLE_ID config variable is required.")

table = get_table(table_id)

# --- Insert a row recording this run ---
started_at = datetime.now(timezone.utc).isoformat()
print(f"Inserting run-start row at {started_at}...")

row = table.insert_row({
    "status": "running",
    "started_at": started_at,
    "result": None,
    "items_processed": 0,
})
row_id = row["id"]
print(f"Row inserted: {row_id[:8]}...")

# --- Simulate processing work ---
items = ["item_a", "item_b", "item_c"]
print(f"Processing {len(items)} items...")
for item in items:
    print(f"  Processed: {item}")

# --- Update the row with results ---
finished_at = datetime.now(timezone.utc).isoformat()
table.update_row(row_id, {
    "status": "success",
    "started_at": started_at,
    "finished_at": finished_at,
    "result": "all items processed",
    "items_processed": len(items),
})
print(f"Row updated with results.")

# --- Verify by reading back ---
rows = table.get_rows()
print(f"\nTable now has {len(rows)} row(s).")
print("Done.")
