"""
FastAPI routing and endpoints for the VFX Event Ingestion subsystem.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.events.redis_client import check_redis_health
from backend.events.schemas import (
    BatchIngestionRequest,
    BatchIngestionResponse,
    HealthResponse,
    IngestionResponse,
    RawEventPayload,
)
from backend.events.service import EventIngestionService
from backend.events.timestamps import format_iso8601_utc, now_utc
from backend.events.validator import EventValidationError

router = APIRouter(prefix="/api/v1", tags=["Events"])

# Module-level default service instance (can be overridden by dependency injection)
_global_service: Optional[EventIngestionService] = None


def get_event_service(request: Request) -> EventIngestionService:
    """FastAPI dependency to retrieve or initialize the EventIngestionService."""
    global _global_service
    # If service was attached to app state, use it
    if hasattr(request.app.state, "event_service"):
        return request.app.state.event_service
    if _global_service is None:
        _global_service = EventIngestionService()
    return _global_service


def set_global_service(service: EventIngestionService) -> None:
    """Set the service instance globally (for testing or bootstrap)."""
    global _global_service
    _global_service = service


from backend.common.logging import correlation_id_ctx, event_id_ctx

@router.post(
    "/events",
    response_model=IngestionResponse,
    summary="Ingest a raw VFX event",
    description="Validates, normalizes, deduplicates, and dispatches a raw VFX event to Redis Streams.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_event(
    payload: RawEventPayload,
    response: Response,
    service: EventIngestionService = Depends(get_event_service),
) -> IngestionResponse:
    try:
        result = await service.ingest_event(payload)
        if result.event_id:
            event_id_ctx.set(result.event_id)
        if result.correlation_id:
            correlation_id_ctx.set(result.correlation_id)
        if result.duplicate:
            # Idempotent duplicates return 200 OK instead of 202 Accepted
            response.status_code = status.HTTP_200_OK
        else:
            response.status_code = status.HTTP_202_ACCEPTED
        return result
    except EventValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "EventValidationError", "message": exc.message, "field": exc.field, "details": exc.details},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "IngestionFailure", "message": str(exc)},
        ) from exc


@router.post(
    "/events/batch",
    response_model=BatchIngestionResponse,
    summary="Ingest multiple VFX events",
    description="Batch ingestion endpoint for multiple events.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_batch(
    batch: BatchIngestionRequest,
    service: EventIngestionService = Depends(get_event_service),
) -> BatchIngestionResponse:
    try:
        return await service.ingest_batch(batch)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "BatchIngestionFailure", "message": str(exc)},
        ) from exc


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service status, database connectivity, and Redis connectivity.",
)
async def health_check(
    service: EventIngestionService = Depends(get_event_service),
) -> HealthResponse:
    from sqlalchemy import text
    from backend.database.session import engine

    # Check database connectivity
    db_connected = False
    db_name = None
    db_dialect = engine.url.drivername
    try:
        with engine.connect() as conn:
            db_name = conn.execute(text("SELECT current_database();")).scalar()
            db_connected = True
    except Exception:
        db_connected = False

    # Check Redis connectivity
    is_redis_healthy = await check_redis_health(service.redis_client)

    overall_status = "healthy" if db_connected else "degraded"

    return HealthResponse(
        status=overall_status,
        redis_connected=is_redis_healthy,
        database_connected=db_connected,
        database_name=db_name,
        database_dialect=db_dialect,
        service="vfx-event-ingestion",
        timestamp=format_iso8601_utc(now_utc()),
    )

