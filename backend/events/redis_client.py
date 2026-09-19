"""
Redis connection and lifecycle management for the VFX event layer.
Supports both real Redis server and in-memory fakeredis for self-contained testing.
"""

import os
from typing import Optional
import redis.asyncio as aioredis


def get_redis_url() -> str:
    """Retrieve Redis connection URL from environment or default to local."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def create_redis_client(
    url: Optional[str] = None,
    use_fake: bool = False,
) -> aioredis.Redis:
    """
    Create an asynchronous Redis client.
    If use_fake is True, instantiates fakeredis.aioredis.FakeRedis.
    """
    if use_fake:
        import fakeredis.aioredis
        return fakeredis.aioredis.FakeRedis(decode_responses=True)

    redis_url = url or get_redis_url()
    return aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


async def check_redis_health(client: Optional[aioredis.Redis]) -> bool:
    """Check if Redis connection is alive and responsive."""
    if client is None:
        return False
    try:
        res = await client.ping()
        return bool(res)
    except Exception:
        return False
