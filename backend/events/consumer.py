"""
Redis Streams Consumer for normalized VFX events.
Supports consumer groups, message acknowledgment, retry limits, and dead-letter routing.
"""

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional
import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from backend.events.dead_letter import DeadLetterHandler
from backend.events.schemas import CanonicalEvent

logger = logging.getLogger("vfx.events.consumer")


class EventConsumer:
    """
    Asynchronous Redis Streams consumer group worker.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        stream_name: str = "vfx.events.normalized",
        group_name: str = "vfx-incident-detectors",
        consumer_name: str = "worker-1",
        dead_letter_handler: Optional[DeadLetterHandler] = None,
        max_retries: int = 3,
    ):
        self.client = redis_client
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.dlq_handler = dead_letter_handler or DeadLetterHandler(redis_client=redis_client)
        self.max_retries = max_retries
        self._running = False
        self._retry_tracker: dict[str, int] = {}

    async def init_group(self) -> None:
        """Create consumer group if it doesn't already exist."""
        try:
            await self.client.xgroup_create(
                name=self.stream_name,
                groupname=self.group_name,
                id="0",
                mkstream=True,
            )
            logger.info("Created consumer group '%s' on stream '%s'", self.group_name, self.stream_name)
        except ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Group already exists, which is normal
                pass
            else:
                raise

    def parse_stream_message(self, raw_data: dict[str, Any]) -> CanonicalEvent:
        """Extract and parse CanonicalEvent from Redis stream field dictionary."""
        payload_str = raw_data.get("payload")
        if not payload_str:
            raise ValueError("Stream message missing 'payload' field")

        if isinstance(payload_str, bytes):
            payload_str = payload_str.decode("utf-8")

        parsed_json = json.loads(payload_str)
        return CanonicalEvent.model_validate(parsed_json)

    async def read_and_process_batch(
        self,
        handler: Callable[[CanonicalEvent], Awaitable[None]],
        count: int = 10,
        block_ms: int = 1000,
        read_pending: bool = False,
    ) -> int:
        """
        Poll one batch from Redis stream, process, and acknowledge.
        If read_pending is True, reads unacknowledged messages from consumer's PEL ("0").
        Otherwise, reads newly arrived messages (">").
        Returns number of messages processed.
        """
        stream_target = "0" if read_pending else ">"
        try:
            entries = await self.client.xreadgroup(
                groupname=self.group_name,
                consumername=self.consumer_name,
                streams={self.stream_name: stream_target},
                count=count,
                block=block_ms if not read_pending else 0,
            )
        except Exception as exc:
            logger.error("Error reading from Redis Stream '%s': %s", self.stream_name, exc)
            return 0

        if not entries:
            return 0

        processed_count = 0
        for stream_key, messages in entries:
            for message_id, raw_fields in messages:
                msg_id_str = message_id.decode("utf-8") if isinstance(message_id, bytes) else str(message_id)
                current_retries = self._retry_tracker.get(msg_id_str, 0)

                try:
                    event = self.parse_stream_message(raw_fields)
                    await handler(event)
                    # Acknowledge on successful processing
                    await self.client.xack(self.stream_name, self.group_name, message_id)
                    self._retry_tracker.pop(msg_id_str, None)
                    processed_count += 1
                except Exception as exc:
                    current_retries += 1
                    self._retry_tracker[msg_id_str] = current_retries
                    logger.warning(
                        "Failed processing message %s (attempt %d/%d): %s",
                        msg_id_str,
                        current_retries,
                        self.max_retries,
                        exc,
                    )

                    if current_retries >= self.max_retries:
                        # Route poison pill to DLQ and ACK from main stream
                        await self.dlq_handler.route_to_dlq(
                            reason=f"Exceeded max retries ({self.max_retries}). Last error: {exc}",
                            raw_payload=raw_fields,
                            error_class=exc.__class__.__name__,
                            original_stream=self.stream_name,
                            original_message_id=msg_id_str,
                            retry_count=current_retries,
                        )
                        await self.client.xack(self.stream_name, self.group_name, message_id)
                        self._retry_tracker.pop(msg_id_str, None)
                        logger.error("Message %s moved to DLQ after %d retries", msg_id_str, current_retries)

        return processed_count

    async def start_listening(
        self,
        handler: Callable[[CanonicalEvent], Awaitable[None]],
        poll_interval_seconds: float = 0.1,
    ) -> None:
        """Run consumer loop until stop() is called."""
        await self.init_group()
        self._running = True
        logger.info("Event consumer started on group '%s'...", self.group_name)

        while self._running:
            try:
                await self.read_and_process_batch(handler, count=10, block_ms=1000)
                await asyncio.sleep(poll_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Consumer loop encountered error: %s", e)
                await asyncio.sleep(1.0)

    def stop(self) -> None:
        """Signal the consumer loop to terminate gracefully."""
        self._running = False
