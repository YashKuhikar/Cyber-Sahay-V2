from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Callable, Dict, List
from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter.
    Provides precise per-IP request throttling without requiring Redis.
    """

    def __init__(self):
        self._records: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()
        self._last_cleanup = time.time()

    def _cleanup_stale(self, max_window: int = 3600):
        """Purges keys with no activity in the last hour to prevent memory growth."""
        now = time.time()
        if now - self._last_cleanup > 300:  # Run cleanup every 5 minutes
            cutoff = now - max_window
            keys_to_delete = []
            for key, timestamps in self._records.items():
                active = [t for t in timestamps if t > cutoff]
                if not active:
                    keys_to_delete.append(key)
                else:
                    self._records[key] = active
            for k in keys_to_delete:
                del self._records[k]
            self._last_cleanup = now

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """
        Checks if the request is permitted under the rate limit.
        Returns:
            (is_allowed: bool, retry_after_seconds: int)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            self._cleanup_stale(max_window=window_seconds * 2)
            timestamps = self._records[key]

            # Filter out timestamps outside the sliding window
            valid_timestamps = [t for t in timestamps if t > window_start]

            if len(valid_timestamps) >= max_requests:
                # Rate limit exceeded - oldest timestamp in window determines retry-after
                oldest_in_window = valid_timestamps[0]
                retry_after = int(window_seconds - (now - oldest_in_window)) + 1
                self._records[key] = valid_timestamps
                return False, max(1, retry_after)

            # Record current request
            valid_timestamps.append(now)
            self._records[key] = valid_timestamps
            return True, 0

    def reset(self):
        """Resets all recorded rate limit state (useful for tests)."""
        with self._lock:
            self._records.clear()


# Global Singleton Limiter Instance
_global_limiter = SlidingWindowRateLimiter()
RateLimiter = _global_limiter


def get_client_ip(request: Request) -> str:
    """Extracts client IP address respecting reverse-proxy X-Forwarded-For headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in list is original client
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def rate_limit(max_requests: int, window_seconds: int = 60) -> Callable:
    """
    FastAPI dependency generator for route-level rate limiting.

    Example:
        @router.post("/login", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))])
    """
    async def dependency(request: Request):
        client_ip = get_client_ip(request)
        endpoint_key = f"{client_ip}:{request.scope.get('path', '')}"

        allowed, retry_after = _global_limiter.is_allowed(
            key=endpoint_key,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds}s. Please retry in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
