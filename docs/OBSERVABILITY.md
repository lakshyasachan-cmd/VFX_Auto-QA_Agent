# VFX Mission Control — Observability, Tracing & Reliability Architecture

This document establishes the observability architecture, distributed tracing schemas, structured JSON logging, resilience policies, and audit trails for **VFX Mission Control**.

---

## 1. Unified Tracing & Correlation Lineage

Every incident lifecycle maintains an unbroken, cryptographically auditable chain of custody linking telemetry across distributed asynchronous stages:

```
incident_id
    ↓
event_id (Canonical Event & Correlation Hash)
    ↓
agent_run_id (Supervisor & Specialist Dispatch Trace)
    ↓
reasoning_id (Gemini Root Cause Synthesis)
    ↓
remediation_id (Deterministic Plan Proposal)
    ↓
approval_id (Policy Auto-Approve or Human Approval Record)
    ↓
mcp_execution_id (Controlled Tool Dispatch & watsonx Skill Execution)
    ↓
audit_id (Immutable Audit Record)
```

### Trace Context Propagation
Distributed context is managed via Python `contextvars` in [`backend/common/logging.py`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/common/logging.py):
- `correlation_id_ctx`: Trace ID across HTTP, Redis Streams, and external webhooks.
- `incident_id_ctx`: Aggregate incident identifier (`inc-<hash>`).
- `event_id_ctx`: Ingested canonical event ID.
- `agent_run_id_ctx`: Specialist investigation execution run ID.
- `reasoning_id_ctx`: Root cause synthesis ID.
- `remediation_id_ctx`: Remediation plan proposal ID.
- `approval_id_ctx`: Governance checkpoint ID.
- `mcp_execution_id_ctx`: Model Context Protocol execution ID.

HTTP endpoints automatically ingest and reflect `X-Correlation-ID` and `X-Incident-ID` in response headers.

---

## 2. Structured JSON Logging

Logs are formatted as structured JSON for ingestion by studio log collectors (Elasticsearch, Loki, Datadog):

```json
{
  "timestamp": "2026-09-09T00:15:30.123456Z",
  "level": "INFO",
  "logger": "vfx.mcp.gateway",
  "message": "Tool 'retry_render_job' executed successfully for job-1042.",
  "trace_context": {
    "correlation_id": "c7a8b9e1-2f34-4a5b-9c12-34567890abcd",
    "incident_id": "inc-c7a8b9e1",
    "event_id": "evt-c7a8b9e1",
    "agent_run_id": "run-sup-c7a8b9e1",
    "reasoning_id": "rsn-c7a8b9e1",
    "remediation_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "approval_id": "appr-8f12a34b",
    "mcp_execution_id": "exec-6b6da33d-779c-4f42-ae4a-00fdcd5ed690"
  },
  "extra": {
    "job_id": "job-1042",
    "node_class": "standard",
    "api_key": "[REDACTED]"
  }
}
```

### Credential Redaction Invariant
The formatter automatically sanitizes:
- Any dictionary key matching `api_key`, `token`, `password`, `secret`, `authorization`.
- Any string containing `bearer <token>`, `api_key=...`, or `password=...`.

---

## 3. Resilience & Failure Handling

### 3.1 Timeouts & Agent Containment
- **Supervisor Delegation**: In [`SupervisorAgent._execute_specialist_safely`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/agents/supervisor/supervisor_agent.py#L80-L135), individual specialists are executed within strict timeouts (`timeout_seconds`, default 15s) using `asyncio.wait_for()`.
- **Fault Containment**: If an individual specialist times out or raises an unhandled exception, the supervisor catches the error, marks the specialist status as `TIMED_OUT` or `FAILED`, and proceeds with partial findings without crashing the platform.

### 3.2 Retries with Exponential Backoff
- Implemented in [`WatsonxOrchestrateClient`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/integrations/watsonx/client.py).
- Transient errors (`HTTP 429`, `502`, `503`, `504`) and network timeouts automatically trigger exponential backoff:
  $$t_{\text{sleep}} = \text{backoff\_factor} \times 2^{\text{attempt} - 1}$$
- Non-retryable errors (e.g. `HTTP 401 Unauthorized`, `HTTP 400 Bad Request`) fail immediately without futile retries.

### 3.3 Circuit Breakers
- Implemented in [`backend/common/circuit_breaker.py`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/common/circuit_breaker.py).
- Monitors external integration failure rates.
- If external services fail 3 consecutive times, the circuit trips to `OPEN`, immediately rejecting outbound requests with `CircuitBreakerOpenException` for 30 seconds before testing recovery in `HALF_OPEN`.

---

## 4. Database Transaction Boundaries

All mutations across incidents, evidence, agent runs, reasoning, remediation plans, approvals, and audit records use the [`db_transaction()`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/common/transaction.py) context manager:

```python
from backend.common.transaction import db_transaction

with db_transaction() as session:
    session.add(incident)
    session.add(audit_log)
    # Automatically commits on exit; automatically rolls back on any exception
```

Guarantees:
- Atomicity of state changes.
- Rollback containment preventing partial or corrupted data.
- Immutable audit trail recording before commit completion.
