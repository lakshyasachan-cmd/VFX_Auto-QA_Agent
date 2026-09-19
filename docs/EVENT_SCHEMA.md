# VFX Event Schema Specification

## 1. Overview
The VFX Pipeline Incident Investigation & Remediation Platform utilizes an event-driven architecture. 
External VFX production systems (Deadline, Tractor, OpenCue, ShotGrid, Asset Storage servers) produce heterogeneous events. 
The Event Ingestion & Normalization subsystem validates, sanitizes, and normalizes these raw incoming payloads into a **Canonical Normalized VFX Event**.

The event layer is strictly decoupled from LLMs, agents, and remediation logic.

---

## 2. Event Types & Severities

### Supported Event Types
1. `RENDER_JOB_FAILED`: A render task/job failed on the render farm (e.g., GPU OOM, missing shader, segfault).
2. `RENDER_JOB_COMPLETED`: A render task/job finished rendering successfully.
3. `RENDER_JOB_STARTED`: A render task/job was dispatched and began execution on a node.
4. `NODE_UNHEALTHY`: A compute/render blade reported degraded health (e.g., thermal throttling, high GPU ECC errors, PCIe bus error).
5. `ASSET_VALIDATION_FAILED`: A USD, Alembic, VDB, or texture asset failed validation checks (e.g., broken reference, missing file, version mismatch).
6. `FRAME_CORRUPTION_DETECTED`: A rendered output frame failed sanity inspection (e.g., 0-byte file, invalid header, NaN pixel values, black frame).

### Severities
- `CRITICAL`: Immediate production blockage (e.g., farm node hardware failure, missing critical asset blocking delivery, repeated OOM cascade).
- `HIGH`: Render job failure affecting shot deadline, corrupt frames in main beauty pass.
- `MEDIUM`: Non-blocking asset validation warning, single frame retryable failure.
- `LOW`: Render job started, minor telemetry glitch.
- `INFO`: Informational event such as render job completion or health check pass.

---

## 3. Canonical Event Schema

Every incoming event is normalized into the following schema:

```json
{
  "event_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "correlation_id": "c3059871-332e-4b68-80e9-b5ef7bfb5ab2",
  "idempotency_key": "deadline:job_123:RENDER_JOB_FAILED",
  "source": "deadline",
  "event_type": "RENDER_JOB_FAILED",
  "severity": "HIGH",
  "timestamp": "2026-09-08T16:45:00.000000Z",
  "ingested_at": "2026-09-08T16:45:01.125000Z",
  "project": "Project_A",
  "sequence": "SQ020",
  "shot": "SH010",
  "entity": {
    "entity_type": "job",
    "entity_id": "job_123",
    "project": "Project_A",
    "sequence": "SQ020",
    "shot": "SH010",
    "job_id": "job_123",
    "node_id": "render-node-42",
    "asset_name": null,
    "frame": null
  },
  "error_details": {
    "error_code": "GPU_OUT_OF_MEMORY",
    "message": "CUDA out of memory while allocating 4096MB buffer on render-node-42",
    "exit_code": 137
  },
  "metrics": {
    "vram_used_mb": 24576,
    "vram_total_mb": 24576,
    "ram_used_gb": 64.0
  },
  "metadata": {
    "environment": "production",
    "source_version": "10.3.0"
  },
  "raw_payload_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

---

## 4. Redis Stream Topics

- Primary Stream: `vfx.events.normalized`
- Consumer Group: `vfx-incident-detectors`
- Dead Letter Queue (DLQ): `vfx.events.dlq`
