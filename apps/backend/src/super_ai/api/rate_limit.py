"""In-process per-user sliding-window rate limiting for high-cost endpoints."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import Depends

from super_ai.api.dependencies import current_user
from super_ai.api.responses import ApiErrorException
from super_ai.auth.repositories import UserRecord

_DEFAULT_LIMIT = 10
_DEFAULT_WINDOW_SECONDS = 60


class SlidingWindowLimiter:
    """Thread-safe sliding-window limiter keyed by arbitrary scope strings."""

    def __init__(
        self,
        *,
        limit: int = _DEFAULT_LIMIT,
        window_seconds: float = _DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._limit = max(1, limit)
        self._window = max(0.01, window_seconds)
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        with self._lock:
            timestamps = self._hits.get(key)
            if timestamps is None:
                self._hits[key] = deque([now])
                return True
            while timestamps and now - timestamps[0] >= self._window:
                timestamps.popleft()
            if len(timestamps) >= self._limit:
                return False
            timestamps.append(now)
            return True


def create_rate_limit_dependency(
    scope: str,
    *,
    limit: int = _DEFAULT_LIMIT,
    window_seconds: float = _DEFAULT_WINDOW_SECONDS,
) -> Callable[[UserRecord], None]:
    """Build a FastAPI dependency enforcing a per-user rate limit.

    超限时抛出 ``RATE_LIMIT_EXCEEDED``（HTTP 429）。每个端点独立配额。
    """

    limiter = SlidingWindowLimiter(limit=limit, window_seconds=window_seconds)

    def dependency(user: Annotated[UserRecord, Depends(current_user)]) -> None:
        if not limiter.allow(user.id):
            raise ApiErrorException("RATE_LIMIT_EXCEEDED")

    return dependency
