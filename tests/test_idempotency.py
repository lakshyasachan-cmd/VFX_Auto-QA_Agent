"""
Unit tests for idempotency handling (in-memory and Redis-backed).
"""

import pytest
import fakeredis.aioredis
from backend.events.idempotency import (
    IdempotencyManager,
    MemoryIdempotencyStore,
    RedisIdempotencyStore,
)


@pytest.mark.asyncio
async def test_memory_idempotency_store():
    store = MemoryIdempotencyStore()
    manager = IdempotencyManager(store=store)

    # First attempt -> new
    is_dup, prev = await manager.is_duplicate("key_1", "event_101")
    assert not is_dup
    assert prev is None

    # Second attempt with same key -> duplicate detected
    is_dup2, prev2 = await manager.is_duplicate("key_1", "event_102")
    assert is_dup2
    assert prev2 == "event_101"

    # Different key -> new
    is_dup3, prev3 = await manager.is_duplicate("key_2", "event_201")
    assert not is_dup3
    assert prev3 is None


@pytest.mark.asyncio
async def test_redis_idempotency_store():
    fake_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = RedisIdempotencyStore(fake_client)
    manager = IdempotencyManager(store=store)

    is_dup, prev = await manager.is_duplicate("deadline:job_99:RENDER_FAILED", "evt_1")
    assert not is_dup
    assert prev is None

    is_dup2, prev2 = await manager.is_duplicate("deadline:job_99:RENDER_FAILED", "evt_2")
    assert is_dup2
    assert prev2 == "evt_1"

    await fake_client.aclose()
