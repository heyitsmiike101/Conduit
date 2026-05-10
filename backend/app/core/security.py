"""
Authentication and authorization placeholder.

The users and sessions tables exist in the database from day one, but login
is intentionally not implemented in Iteration 1. This module provides the
dependency stub that all API routes accept today.

When login is enabled (future iteration):
  - Replace get_current_user() with a real token-validation dependency.
  - Make it mandatory (remove the Optional / None return path).
  - Add role-based access checks per route.
  - Use bcrypt for password hashing (never store plaintext passwords).
  - Implement CSRF protection for state-changing endpoints.

Nothing else in the codebase needs to change when this module is updated —
that isolation is the point.
"""

from typing import Optional


# TODO: Implement login.
# Replace this stub with a real FastAPI dependency that:
#   1. Reads the Authorization header (Bearer token).
#   2. Looks up the session in the sessions table.
#   3. Validates expiry.
#   4. Returns the associated User row.
#   5. Raises HTTP 401 if missing or invalid.
def get_current_user() -> Optional[None]:
    """
    Return the currently authenticated user.

    Today this always returns None — the platform is open with no auth.
    Routes that accept this as a dependency are already wired for the future
    where it returns a real User object.
    """
    return None
