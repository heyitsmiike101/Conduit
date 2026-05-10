"""
Example 05 — API Call Logging

Demonstrates logging outbound HTTP calls so they appear in the Conduit
execution log alongside stdout/stderr. This is useful for:
  - Audit trails of external API calls
  - Debugging rate-limit or auth failures
  - Tracking API response times

Each logged call appears as a separate log entry with stream="api" in the
execution log, visible in the Conduit UI.

Run via the Conduit UI after setting the config variables,
or use conduit_fixtures/config.json for local testing.
"""

import time
import httpx
from conduit import get_config, log_api_call

config = get_config()

base_url = config.get("API_BASE_URL", "https://httpbin.org")
api_key = config.get("API_KEY", "")

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

print(f"Making API calls to {base_url}...")

# --- GET request ---
url = f"{base_url}/get"
t0 = time.time()
try:
    resp = httpx.get(url, headers=headers, timeout=10.0)
    duration_ms = (time.time() - t0) * 1000
    print(f"GET {url} → {resp.status_code} ({duration_ms:.0f}ms)")

    log_api_call(
        method="GET",
        url=url,
        status_code=resp.status_code,
        duration_ms=duration_ms,
        metadata={"content_length": len(resp.content)},
    )
except Exception as exc:
    duration_ms = (time.time() - t0) * 1000
    print(f"GET {url} → ERROR: {exc}")
    log_api_call(
        method="GET",
        url=url,
        status_code=0,
        duration_ms=duration_ms,
        metadata={"error": str(exc)},
    )

# --- POST request ---
url = f"{base_url}/post"
payload = {"source": "conduit", "timestamp": str(time.time())}
t0 = time.time()
try:
    resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
    duration_ms = (time.time() - t0) * 1000
    print(f"POST {url} → {resp.status_code} ({duration_ms:.0f}ms)")

    log_api_call(
        method="POST",
        url=url,
        status_code=resp.status_code,
        duration_ms=duration_ms,
    )
except Exception as exc:
    duration_ms = (time.time() - t0) * 1000
    print(f"POST {url} → ERROR: {exc}")
    log_api_call(
        method="POST",
        url=url,
        status_code=0,
        duration_ms=duration_ms,
        metadata={"error": str(exc)},
    )

print("\nAll API calls logged to the Conduit execution log.")
print("Check the 'API' stream in the execution log view to see them.")
