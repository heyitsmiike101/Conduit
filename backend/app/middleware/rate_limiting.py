"""
Rate limiting middleware — prevents DoS attacks and resource exhaustion.

Uses slowapi (a maintained fork of ratelimit) with in-memory storage.
Limits: 60 requests per minute per IP address by default.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create a global limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],  # 60 requests per minute per IP
    storage_uri="memory://",  # In-memory storage (fast, not persistent)
)
