"""
Example 01 — Hello World

The simplest possible Conduit script. Demonstrates that the runner can
spawn a subprocess, capture its stdout, and record an execution.

Run via the Conduit UI: upload this file, click Run.
"""

from conduit import get_config

config = get_config()

print("Hello from Conduit!")
print(f"Config has {len(config)} variable(s) loaded.")

# Print non-secret config keys (values masked for safety in logs)
for key in sorted(config):
    print(f"  {key} = ***")

print("Script finished successfully.")
