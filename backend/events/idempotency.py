"""
Idempotency handling for the VFX event ingestion layer.
Ensures identical events from external retry mechanisms are not double-processed.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional
import redis.asyncio as aioredis


class BaseIdempotencyStore(ABC):
    """Abstract interface for checking and storing idempotency keys."""

    @abstractmethod
    async def check_and_set(self, key: str, value: str, ttl_seconds: int = 86400) -> tuple[bool, Optional[str]]:
        """
        Atomically check if key exists.
        If it exists, returns (True, existing_value).
        If it does not exist, stores value with TTL and returns (False, None).
        """
        pass

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Retrieve stored value for key."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear store (primarily for testing)."""
        pass


class MemoryIdempotencyStore(BaseIdempotencyStore):
    """
    In-memory idempotency store with TTL expiration.
    Ideal for local testing, mock setups, and unit test environments.
    """

    def __init__(self):
        # key -> (value, expiry_time)
        self._store: dict[str, tuple[str, float]] = {}

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

    async def check_and_set(self, key: str, value: str, ttl_seconds: int = 86400) -> tuple[bool, Optional[str]]:
        self._cleanup_expired()
        now = time.time()
        if key in self._store:
            existing_val, exp = self._store[key]
            if now <= exp:
                return True, existing_val

        # Not present or expired: set
        self._store[key] = (value, now + ttl_seconds)
        return False, None

    async def get(self, key: str) -> Optional[str]:
        self._cleanup_expired()
        now = time.time()
        if key in self._store:
            val, exp = self._store[key]
            if now <= exp:
                return val
        return None

    async def clear(self) -> None:
        self._store.clear()


class RedisIdempotencyStore(BaseIdempotencyStore):
    """
    Production-grade Redis-backed idempotency store using atomic SET NX EX.
    """

    def __init__(self, redis_client: aioredis.Redis, key_prefix: str = "vfx:idempotency:"):
        self.client = redis_client
        self.key_prefix = key_prefix

    def _format_key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"

    async def check_and_set(self, key: str, value: str, ttl_seconds: int = 86400) -> tuple[bool, Optional[str]]:
        full_key = self._format_key(key)
        # Attempt atomic set if not exists
        acquired = await self.client.set(full_key, value, ex=ttl_seconds, nx=True)
        if acquired:
            return False, None

        # Key already existed, fetch previous value
        existing = await self.client.get(full_key)
        if isinstance(existing, bytes):
            existing = existing.decode("utf-8")
        return True, existing

    async def get(self, key: str) -> Optional[str]:
        full_key = self._format_key(key)
        val = await self.client.get(full_key)
        if val is None:
            return None
        if isinstance(val, bytes):
            return val.decode("utf-8")
        return str(val)

    async def clear(self) -> None:
        # Clear keys matching prefix
        pattern = f"{self.key_prefix}*"
        cursor = 0
        while True:
            cursor, keys = await self.client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await self.client.delete(*keys)
            if cursor == 0:
                break


class IdempotencyManager:
    """
    High-level idempotency service.
    """

    def __init__(self, store: Optional[BaseIdempotencyStore] = None, default_ttl_seconds: int = 86400):
        self.store = store or MemoryIdempotencyStore()
        self.default_ttl = default_ttl_seconds

    async def is_duplicate(self, key: str, event_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if event key has been seen.
        Returns:
            (is_duplicate, previous_event_id_or_none)
        """
        is_dup, prev_val = await self.store.check_and_set(key, event_id, ttl_seconds=self.default_ttl)
        return is_dup, prev_val
