"""
Request size limiting middleware — prevents disk exhaustion attacks.

Enforces maximum request/upload sizes:
- File uploads: 100 MB per file
- JSON payloads: 10 MB
"""

from fastapi import Request, HTTPException
import logging

logger = logging.getLogger(__name__)

# Size limits in bytes
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_JSON_SIZE = 10 * 1024 * 1024     # 10 MB


async def request_size_limiter(request: Request, call_next):
    """
    Middleware that validates Content-Length header before processing.

    Rejects requests that exceed size limits to prevent resource exhaustion.
    """
    content_length = request.headers.get("content-length")

    if content_length:
        try:
            size = int(content_length)

            # File uploads to /scripts/{id}/upload or /scripts/{id}/files
            if "/upload" in request.url.path or "/files" in request.url.path:
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Request too large. Maximum upload size is {MAX_UPLOAD_SIZE // (1024*1024)} MB.",
                    )
            # All other requests
            else:
                if size > MAX_JSON_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Request too large. Maximum payload size is {MAX_JSON_SIZE // (1024*1024)} MB.",
                    )
        except ValueError:
            logger.warning("Invalid Content-Length header: %s", content_length)

    response = await call_next(request)
    return response
