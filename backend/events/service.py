"""
Event Ingestion Service coordinating validation, normalization, idempotency, and stream publishing.
Decoupled from downstream AI, LLMs, or incident resolution logic.
"""

import logging
from typing import Any, Optional
import redis.asyncio as aioredis

from backend.events.dead_letter import DeadLetterHandler
from backend.events.idempotency import BaseIdempotencyStore, IdempotencyManager, MemoryIdempotencyStore, RedisIdempotencyStore
from backend.events.normalizer import EventNormalizer
from backend.events.producer import EventProducer
from backend.events.schemas import (
    BatchIngestionRequest,
    BatchIngestionResponse,
    IngestionResponse,
    RawEventPayload,
)
from backend.events.validator import EventValidationError

logger = logging.getLogger("vfx.events.service")


class EventIngestionService:
    """
    Core service orchestrating the event ingestion pipeline.
    """

    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
        normalizer: Optional[EventNormalizer] = None,
        idempotency_store: Optional[BaseIdempotencyStore] = None,
        producer: Optional[EventProducer] = None,
        dead_letter_handler: Optional[DeadLetterHandler] = None,
        stream_name: str = "vfx.events.normalized",
    ):
        self.redis_client = redis_client
        self.normalizer = normalizer or EventNormalizer()
        self.stream_name = stream_name

        # Setup idempotency store
        if idempotency_store is not None:
            self.idempotency = IdempotencyManager(store=idempotency_store)
        elif redis_client is not None:
            self.idempotency = IdempotencyManager(store=RedisIdempotencyStore(redis_client))
        else:
            self.idempotency = IdempotencyManager(store=MemoryIdempotencyStore())

        # Setup producer
        if producer is not None:
            self.producer = producer
        elif redis_client is not None:
            self.producer = EventProducer(redis_client, stream_name=stream_name)
        else:
            self.producer = None

        # Setup DLQ
        self.dlq = dead_letter_handler or DeadLetterHandler(redis_client=redis_client)

    async def ingest_event(self, raw: RawEventPayload | dict[str, Any]) -> IngestionResponse:
        """
        Process a single incoming raw event:
        1. Normalize into CanonicalEvent (which executes validation)
        2. Check for duplicate using IdempotencyManager
        3. Publish to Redis Streams if new
        4. Return IngestionResponse
        """
        try:
            canonical = self.normalizer.normalize(raw)
        except EventValidationError as val_err:
            logger.warning("Event validation rejected: %s", val_err)
            # Route unparseable / invalid payload to DLQ for auditing
            await self.dlq.route_to_dlq(
                reason=f"Validation failed: {val_err}",
                raw_payload=raw if isinstance(raw, dict) else raw.model_dump(),
                error_class="EventValidationError",
            )
            raise

        # 2. Idempotency check
        is_dup, prev_id = await self.idempotency.is_duplicate(
            key=canonical.idempotency_key,
            event_id=canonical.event_id,
        )

        if is_dup:
            logger.info("Duplicate event ignored: key=%s, prev_event_id=%s", canonical.idempotency_key, prev_id)
            return IngestionResponse(
                status="duplicate_ignored",
                event_id=prev_id or canonical.event_id,
                correlation_id=canonical.correlation_id,
                idempotency_key=canonical.idempotency_key,
                duplicate=True,
                normalized_event=None,
                message="Duplicate event ignored via idempotency key",
            )

        # 3. Publish to Redis Stream
        if self.producer is not None:
            try:
                await self.producer.publish(canonical)
            except Exception as pub_err:
                logger.error("Failed to publish to stream %s: %s", self.stream_name, pub_err)
                await self.dlq.route_to_dlq(
                    reason=f"Failed to publish to stream: {pub_err}",
                    raw_payload=canonical.model_dump(mode="json"),
                    error_class=pub_err.__class__.__name__,
                )
                raise

        return IngestionResponse(
            status="accepted",
            event_id=canonical.event_id,
            correlation_id=canonical.correlation_id,
            idempotency_key=canonical.idempotency_key,
            duplicate=False,
            normalized_event=canonical,
            message="Event accepted and published to stream",
        )

    async def ingest_batch(self, batch: BatchIngestionRequest | list[dict[str, Any]]) -> BatchIngestionResponse:
        """
        Process a collection of events.
        """
        events = batch.events if isinstance(batch, BatchIngestionRequest) else batch
        results: list[IngestionResponse] = []
        accepted = 0
        duplicates = 0
        failed = 0

        for raw in events:
            try:
                resp = await self.ingest_event(raw)
                results.append(resp)
                if resp.duplicate:
                    duplicates += 1
                else:
                    accepted += 1
            except Exception as e:
                failed += 1
                results.append(
                    IngestionResponse(
                        status="failed",
                        event_id="none",
                        correlation_id="none",
                        idempotency_key="none",
                        duplicate=False,
                        normalized_event=None,
                        message=str(e),
                    )
                )

        return BatchIngestionResponse(
            accepted_count=accepted,
            duplicate_count=duplicates,
            failed_count=failed,
            results=results,
        )
