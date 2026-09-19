"""
Redis Streams Producer for normalized VFX events.
Publishes CanonicalEvent models to Redis Stream (e.g., 'vfx.events.normalized').
"""

import json
import redis.asyncio as aioredis

from backend.events.schemas import CanonicalEvent


class EventProducerError(RuntimeError):
    """Raised when publishing to Redis Streams fails."""
    pass


class EventProducer:
    """
    Asynchronous Redis Streams producer for normalized VFX events.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        stream_name: str = "vfx.events.normalized",
        max_stream_length: int = 100000,
    ):
        self.client = redis_client
        self.stream_name = stream_name
        self.max_stream_length = max_stream_length

    async def publish(self, event: CanonicalEvent) -> str:
        """
        Publish a single CanonicalEvent to the Redis stream.
        Returns the Redis message ID.
        """
        try:
            # Serialize the canonical event model to JSON string
            payload_json = json.dumps(event.model_dump(mode="json"), default=str)

            # Redis Streams entry fields: payload + key metadata for fast filtering
            fields = {
                "event_id": event.event_id,
                "correlation_id": event.correlation_id,
                "idempotency_key": event.idempotency_key,
                "source": event.source.value if hasattr(event.source, "value") else str(event.source),
                "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                "severity": event.severity.value if hasattr(event.severity, "value") else str(event.severity),
                "payload": payload_json,
            }

            msg_id = await self.client.xadd(
                self.stream_name,
                fields,
                maxlen=self.max_stream_length,
                approximate=True,
            )
            if isinstance(msg_id, bytes):
                return msg_id.decode("utf-8")
            return str(msg_id)
        except Exception as exc:
            raise EventProducerError(f"Failed to publish event {event.event_id} to {self.stream_name}: {exc}") from exc

    async def publish_batch(self, events: list[CanonicalEvent]) -> list[str]:
        """
        Publish multiple events sequentially or via pipeline.
        Returns list of message IDs.
        """
        if not events:
            return []

        message_ids = []
        # Pipeline for efficiency
        pipeline = self.client.pipeline()
        for event in events:
            payload_json = json.dumps(event.model_dump(mode="json"), default=str)
            fields = {
                "event_id": event.event_id,
                "correlation_id": event.correlation_id,
                "idempotency_key": event.idempotency_key,
                "source": event.source.value if hasattr(event.source, "value") else str(event.source),
                "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                "severity": event.severity.value if hasattr(event.severity, "value") else str(event.severity),
                "payload": payload_json,
            }
            pipeline.xadd(self.stream_name, fields, maxlen=self.max_stream_length, approximate=True)

        results = await pipeline.execute()
        for r in results:
            if isinstance(r, bytes):
                message_ids.append(r.decode("utf-8"))
            else:
                message_ids.append(str(r))
        return message_ids
