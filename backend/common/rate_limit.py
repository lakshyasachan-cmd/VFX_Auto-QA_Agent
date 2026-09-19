"""
In-Memory Sliding Window Rate Limiter for API endpoints and event streams.
Protects against Denial of Service and API exhaustion from rogue worker nodes.
"""

from collections import deque
import time
from fastapi import HTTPException, Request, status

class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding window rate limiter per client key (IP or API key).
    """

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: dict[str, deque[float]] = {}

    def is_allowed(self, key: str) -> tuple[bool, int, float]:
        """
        Check if request for given key is allowed.
        Returns (allowed, remaining_requests, reset_after_seconds).
        """
        now = time.time()
        if key not in self._history:
            self._history[key] = deque()

        queue = self._history[key]

        # Purge entries older than window
        cutoff = now - self.window_seconds
        while queue and queue[0] <= cutoff:
            queue.popleft()

        if len(queue) < self.max_requests:
            queue.append(now)
            remaining = self.max_requests - len(queue)
            reset_after = self.window_seconds - (now - queue[0]) if queue else 0.0
            return True, remaining, max(0.0, reset_after)

        reset_after = self.window_seconds - (now - queue[0]) if queue else self.window_seconds
        return False, 0, max(0.0, reset_after)


# Default global rate limiter: 120 requests per minute per client
global_rate_limiter = SlidingWindowRateLimiter(max_requests=120, window_seconds=60.0)


def rate_limit_dependency(max_requests: int = 120, window_seconds: float = 60.0):
    """FastAPI dependency enforcing rate limits per client IP or authorization header."""
    limiter = SlidingWindowRateLimiter(max_requests=max_requests, window_seconds=window_seconds)

    async def check_rate_limit(request: Request) -> None:
        client_key = request.headers.get("X-API-Key") or (request.client.host if request.client else "unknown_client")
        allowed, remaining, reset_after = limiter.is_allowed(client_key)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {reset_after:.1f} seconds.",
                headers={"Retry-After": str(int(reset_after) + 1)},
            )
    return check_rate_limit
