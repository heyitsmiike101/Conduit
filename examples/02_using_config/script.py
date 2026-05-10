"""
Example 02 — Using Config Variables

Demonstrates reading configuration variables injected by the Conduit runner.
Config variables are set in the Conduit UI (Variables page) and decrypted
automatically before being passed to the script.

Typical use cases:
  - API keys and tokens
  - Environment names (dev/staging/prod)
  - Database connection strings
  - Feature flags

Run via the Conduit UI after creating the variables below,
or use conduit_fixtures/config.json for local testing.
"""

from conduit import get_config

config = get_config()

# Read variables with sensible defaults for missing keys
api_key = config.get("API_KEY", "")
environment = config.get("ENV", "dev")
base_url = config.get("BASE_URL", "https://api.example.com")

if not api_key:
    print("WARNING: API_KEY not set — authentication will fail")
else:
    # Never print the actual key — just confirm it's present
    print(f"API_KEY loaded ({len(api_key)} chars)")

print(f"Environment: {environment}")
print(f"Base URL: {base_url}")

# Simulate work
print(f"Would call {base_url}/endpoint with API key...")
print("Done.")
