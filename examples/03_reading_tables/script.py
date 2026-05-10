"""
Example 03 — Reading from InfoTables

Demonstrates reading rows from a Conduit InfoTable.

Prerequisites in the Conduit UI:
  1. Create an InfoTable (e.g. named "products")
  2. Insert some rows via the UI
  3. Enable can_read_tables permission for this script
  4. Set the TABLE_ID variable to the table's ID

This example reads all rows and prints a summary.
"""

import json
from conduit import get_config, get_table

config = get_config()

# The table ID is stored as a config variable so it doesn't need to be
# hardcoded in the script — changing it in the UI updates all scripts at once.
table_id = config.get("TABLE_ID")
if not table_id:
    raise RuntimeError(
        "TABLE_ID config variable is required. "
        "Set it in the Conduit UI to the InfoTable ID you want to read."
    )

print(f"Reading table: {table_id}")

table = get_table(table_id)
rows = table.get_rows()

print(f"Found {len(rows)} row(s):\n")

for row in rows:
    row_data = json.loads(row["row_data_json"])
    print(f"  Row {row['id'][:8]}...: {json.dumps(row_data, indent=4)}")

print("\nRead complete.")
