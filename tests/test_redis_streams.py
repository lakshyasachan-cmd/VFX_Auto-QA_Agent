"""
Integration tests for Redis Streams Producer and Consumer with consumer groups.
"""

import pytest
import fakeredis.aioredis

from backend.events.consumer import EventConsumer
from backend.events.dead_letter import DeadLetterHandler
from backend.events.normalizer import EventNormalizer
from backend.events.producer import EventProducer
from backend.events.schemas import CanonicalEvent


@pytest.fixture
def normalizer():
    return EventNormalizer()


@pytest.fixture
async def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_producer_and_consumer_roundtrip(fake_redis, normalizer):
    stream_name = "test.vfx.normalized"
    group_name = "test-group"

    producer = EventProducer(fake_redis, stream_name=stream_name)
    consumer = EventConsumer(
        fake_redis,
        stream_name=stream_name,
        group_name=group_name,
        consumer_name="worker-test",
    )

    # Initialize consumer group
    await consumer.init_group()

    # Produce an event
    raw = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": "Project_A",
        "sequence": "SQ020",
        "shot": "SH010",
        "job_id": "job_123",
        "node_id": "render-node-42",
        "error_code": "GPU_OUT_OF_MEMORY",
    }
    canonical = normalizer.normalize(raw)
    msg_id = await producer.publish(canonical)
    assert msg_id is not None

    # Consume and verify
    consumed_events: list[CanonicalEvent] = []

    async def sample_handler(event: CanonicalEvent):
        consumed_events.append(event)

    processed_count = await consumer.read_and_process_batch(sample_handler, count=10, block_ms=500)
    assert processed_count == 1
    assert len(consumed_events) == 1
    rec = consumed_events[0]
    assert rec.event_id == canonical.event_id
    assert rec.entity.job_id == "job_123"
    assert rec.error_details.error_code == "GPU_OUT_OF_MEMORY"


@pytest.mark.asyncio
async def test_consumer_poison_pill_routed_to_dlq(fake_redis, normalizer):
    stream_name = "test.poison.stream"
    dlq_stream = "test.poison.dlq"
    group_name = "test-poison-group"

    dlq_handler = DeadLetterHandler(redis_client=fake_redis, dlq_stream_name=dlq_stream)
    producer = EventProducer(fake_redis, stream_name=stream_name)
    consumer = EventConsumer(
        fake_redis,
        stream_name=stream_name,
        group_name=group_name,
        consumer_name="poison-worker",
        dead_letter_handler=dlq_handler,
        max_retries=2,
    )

    await consumer.init_group()

    # Produce event
    canonical = normalizer.normalize({
        "source": "tractor",
        "event_type": "NODE_UNHEALTHY",
        "node_id": "bad-node",
    })
    await producer.publish(canonical)

    async def failing_handler(event: CanonicalEvent):
        raise RuntimeError("Simulated processing failure")

    # First attempt -> fails, retry tracker = 1
    await consumer.read_and_process_batch(failing_handler, count=1, block_ms=100)
    # Second attempt (processing pending unacked message) -> fails, retry tracker = 2 (max_retries), routes to DLQ and acks
    await consumer.read_and_process_batch(failing_handler, count=1, block_ms=100, read_pending=True)

    # Check DLQ
    assert len(dlq_handler.in_memory_dlq) == 1
    assert "Simulated processing failure" in dlq_handler.in_memory_dlq[0]["reason"]
