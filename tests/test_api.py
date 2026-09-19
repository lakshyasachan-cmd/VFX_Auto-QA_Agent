"""
Integration tests for the FastAPI event ingestion endpoints.
"""

import pytest
from fastapi.testclient import TestClient
import fakeredis.aioredis

from backend.events.api import set_global_service
from backend.events.idempotency import MemoryIdempotencyStore
from backend.events.normalizer import EventNormalizer
from backend.events.producer import EventProducer
from backend.events.service import EventIngestionService
from backend.main import app


@pytest.fixture
def client():
    # Setup test-isolated service with in-memory idempotency and fake redis
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    idemp_store = MemoryIdempotencyStore()
    producer = EventProducer(fake_redis, stream_name="test.api.stream")
    test_service = EventIngestionService(
        redis_client=fake_redis,
        normalizer=EventNormalizer(),
        idempotency_store=idemp_store,
        producer=producer,
    )
    set_global_service(test_service)
    app.state.event_service = test_service

    with TestClient(app) as test_client:
        yield test_client


def test_post_event_success(client):
    """
    Test endpoint with the exact example event from user prompt:
    {
      "source": "deadline",
      "event_type": "RENDER_JOB_FAILED",
      "project": "Project_A",
      "sequence": "SQ020",
      "shot": "SH010",
      "job_id": "job_123",
      "node_id": "render-node-42",
      "error_code": "GPU_OUT_OF_MEMORY"
    }
    """
    payload = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": "Project_A",
        "sequence": "SQ020",
        "shot": "SH010",
        "job_id": "job_123",
        "node_id": "render-node-42",
        "error_code": "GPU_OUT_OF_MEMORY",
    }
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["duplicate"] is False
    assert data["idempotency_key"] == "deadline:RENDER_JOB_FAILED:job_123:GPU_OUT_OF_MEMORY"
    assert data["normalized_event"]["source"] == "deadline"
    assert data["normalized_event"]["severity"] == "HIGH"
    assert data["normalized_event"]["entity"]["entity_id"] == "job_123"


def test_post_event_duplicate_ignored(client):
    payload = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": "Project_A",
        "sequence": "SQ020",
        "shot": "SH010",
        "job_id": "job_dup_99",
        "node_id": "render-node-42",
        "error_code": "GPU_OUT_OF_MEMORY",
    }
    # First request
    resp1 = client.post("/api/v1/events", json=payload)
    assert resp1.status_code == 202
    assert resp1.json()["duplicate"] is False

    # Second request with identical payload -> 200 OK duplicate ignored
    resp2 = client.post("/api/v1/events", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "duplicate_ignored"
    assert data2["duplicate"] is True


def test_post_event_validation_failure(client):
    # Missing job_id or shot or node_id for RENDER_JOB_FAILED
    payload = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
    }
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data["detail"]
    assert data["detail"]["error"] == "EventValidationError"


def test_post_batch_events(client):
    payload = {
        "events": [
            {
                "source": "deadline",
                "event_type": "RENDER_JOB_STARTED",
                "job_id": "batch_job_1",
                "node_id": "node_01",
            },
            {
                "source": "tractor",
                "event_type": "NODE_UNHEALTHY",
                "node_id": "node_02",
                "error_code": "PCIE_FAIL",
            },
        ]
    }
    response = client.post("/api/v1/events/batch", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["accepted_count"] == 2
    assert data["failed_count"] == 0
    assert len(data["results"]) == 2


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "vfx-event-ingestion"
