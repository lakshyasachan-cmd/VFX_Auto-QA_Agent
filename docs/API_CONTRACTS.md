# VFX Event Ingestion API Contracts

## 1. Webhook & Event Ingestion Endpoints

### Endpoint: Ingest Raw VFX Event
- **Route**: `POST /api/v1/events`
- **Content-Type**: `application/json`
- **Description**: Ingests raw or semi-structured events from VFX production tools (Deadline, Tractor, OpenCue, ShotGrid, custom storage watchers). Validates, deduplicates via idempotency key, normalizes to canonical event schema, and dispatches to Redis Stream `vfx.events.normalized`.

#### Request Body Example (Standard Deadline Render Failure)
```json
{
  "source": "deadline",
  "event_type": "RENDER_JOB_FAILED",
  "project": "Project_A",
  "sequence": "SQ020",
  "shot": "SH010",
  "job_id": "job_123",
  "node_id": "render-node-42",
  "error_code": "GPU_OUT_OF_MEMORY",
  "message": "CUDA out of memory error while loading scene textures",
  "timestamp": "2026-09-08T16:45:00Z"
}
```

#### Response Codes
- `202 Accepted`: Event validated, deduplicated, normalized, and enqueued to Redis Stream.
```json
{
  "status": "accepted",
  "event_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "correlation_id": "c3059871-332e-4b68-80e9-b5ef7bfb5ab2",
  "idempotency_key": "deadline:job_123:RENDER_JOB_FAILED",
  "duplicate": false,
  "normalized_event": { ... }
}
```
- `200 OK`: Duplicate event detected and safely ignored (idempotent duplicate).
```json
{
  "status": "duplicate_ignored",
  "event_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "idempotency_key": "deadline:job_123:RENDER_JOB_FAILED",
  "duplicate": true
}
```
- `422 Unprocessable Entity`: Validation failure on required fields or invalid event type.
- `500 Internal Server Error`: Redis failure, routed to DLQ or error response.

---

### Endpoint: Health Check
- **Route**: `GET /api/v1/health`
- **Description**: Returns operational health of the ingestion service, including Redis connectivity.

---

### Endpoint: Ingest Batch Events
- **Route**: `POST /api/v1/events/batch`
- **Content-Type**: `application/json`
- **Description**: Ingests an array of events in a single transactional batch.
