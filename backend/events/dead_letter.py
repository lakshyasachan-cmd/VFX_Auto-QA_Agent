"""
Dead-letter queue (DLQ) handler for unparseable or repeatedly failing VFX events.
Prevents pipeline stalls (poison pills) while preserving auditability.
"""

import json
from datetime import datetime
from typing import Any, Optional
import redis.asyncio as aioredis

from backend.events.timestamps import format_iso8601_utc, now_utc


class DeadLetterRecord:
    """Represents an unprocessable message sent to DLQ."""

    def __init__(
        self,
        reason: str,
        raw_payload: Any,
        error_class: str,
        original_stream: Optional[str] = None,
        original_message_id: Optional[str] = None,
        retry_count: int = 0,
        failed_at: Optional[datetime] = None,
    ):
        self.reason = reason
        self.raw_payload = raw_payload
        self.error_class = error_class
        self.original_stream = original_stream or "unknown"
        self.original_message_id = original_message_id or "none"
        self.retry_count = retry_count
        self.failed_at = failed_at or now_utc()

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "error_class": self.error_class,
            "original_stream": self.original_stream,
            "original_message_id": self.original_message_id,
            "retry_count": self.retry_count,
            "failed_at": format_iso8601_utc(self.failed_at),
            "raw_payload": self.raw_payload if isinstance(self.raw_payload, str) else json.dumps(self.raw_payload, default=str),
        }


class DeadLetterHandler:
    """
    Publishes failed messages to the configured DLQ stream.
    Supports in-memory buffer if Redis is not yet connected or for testing.
    """

    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
        dlq_stream_name: str = "vfx.events.dlq",
        max_stream_length: int = 50000,
    ):
        self.redis_client = redis_client
        self.dlq_stream_name = dlq_stream_name
        self.max_stream_length = max_stream_length
        # In-memory buffer for test inspection or fallback
        self.in_memory_dlq: list[dict[str, Any]] = []

    async def route_to_dlq(
        self,
        reason: str,
        raw_payload: Any,
        error_class: str = "ProcessingError",
        original_stream: Optional[str] = None,
        original_message_id: Optional[str] = None,
        retry_count: int = 0,
    ) -> str:
        """
        Record poison pill to DLQ.
        Returns the DLQ message ID.
        """
        record = DeadLetterRecord(
            reason=reason,
            raw_payload=raw_payload,
            error_class=error_class,
            original_stream=original_stream,
            original_message_id=original_message_id,
            retry_count=retry_count,
        )
        record_dict = record.to_dict()
        self.in_memory_dlq.append(record_dict)

        if self.redis_client is not None:
            try:
                # Redis Streams XADD fields must be flat strings/bytes
                stream_fields = {k: str(v) for k, v in record_dict.items()}
                msg_id = await self.redis_client.xadd(
                    self.dlq_stream_name,
                    stream_fields,
                    maxlen=self.max_stream_length,
                    approximate=True,
                )
                if isinstance(msg_id, bytes):
                    return msg_id.decode("utf-8")
                return str(msg_id)
            except Exception:
                # Local buffer already has it, log or maintain record
                pass

        return f"mem-dlq-{len(self.in_memory_dlq)}"
