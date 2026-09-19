"""
Unit tests for dead-letter handling.
"""

import pytest
import fakeredis.aioredis
from backend.events.dead_letter import DeadLetterHandler


@pytest.mark.asyncio
async def test_dead_letter_in_memory():
    handler = DeadLetterHandler()
    msg_id = await handler.route_to_dlq(
        reason="Validation failed: missing required node_id",
        raw_payload={"source": "tractor", "event_type": "NODE_UNHEALTHY"},
        error_class="EventValidationError",
        retry_count=0,
    )
    assert msg_id.startswith("mem-dlq-")
    assert len(handler.in_memory_dlq) == 1
    assert handler.in_memory_dlq[0]["error_class"] == "EventValidationError"


@pytest.mark.asyncio
async def test_dead_letter_redis_stream():
    fake_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    handler = DeadLetterHandler(redis_client=fake_client, dlq_stream_name="test.dlq")

    msg_id = await handler.route_to_dlq(
        reason="Poison pill: max retries exceeded",
        raw_payload={"job_id": "job_dead"},
        error_class="ProcessingError",
        retry_count=3,
        original_stream="vfx.events.normalized",
        original_message_id="1694182900000-0",
    )
    assert msg_id is not None
    assert len(handler.in_memory_dlq) == 1

    # Verify message in Redis DLQ stream
    stream_entries = await fake_client.xrange("test.dlq")
    assert len(stream_entries) == 1
    assert stream_entries[0][1]["error_class"] == "ProcessingError"

    await fake_client.aclose()
