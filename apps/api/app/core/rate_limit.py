from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request

from app.core.error_codes import ErrorCodes
from app.core.errors import ApiError


class RateLimitExceededError(ApiError):
    status_code = 429
    code = ErrorCodes.RATE_LIMITED

    def __init__(self, detail: str = "Too many requests. Please try again later.") -> None:
        super().__init__(detail)


_lock = Lock()
_windows: dict[str, list[float]] = defaultdict(list)

# Set to False in conftest.py so the rate limiter is bypassed in tests.
_enabled: bool = True


def _client_key(request: Request, scope: str) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
    return f"{scope}:{ip}"


def check_rate_limit(request: Request, *, scope: str, limit: int, window_seconds: int = 60) -> None:
    if not _enabled:
        return

    key = _client_key(request, scope)
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        hits = _windows[key]
        # Remove timestamps outside the sliding window
        _windows[key] = [t for t in hits if t > cutoff]
        if len(_windows[key]) >= limit:
            raise RateLimitExceededError(
                f"Rate limit exceeded. Maximum {limit} requests per {window_seconds} seconds."
            )
        _windows[key].append(now)
