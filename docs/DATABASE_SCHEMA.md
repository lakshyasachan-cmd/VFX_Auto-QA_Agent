# VFX Platform Database Schema Specification

## 1. Overview & Traceability Lineage

The VFX Pipeline Incident Investigation and Remediation persistence layer is built on **SQLAlchemy 2.x** and **PostgreSQL 16**.
It provides an immutable, relational audit trail for every AI decision.

### Complete AI Decision Traceability Graph
```
Incident (Root Event / Production Anomaly)
   │
   ├── IncidentEvidence (Logs, Telemetry, Scene dumps)
   │
   └── AgentRuns (Multiple iterations / Specialist Agent executions)
         │
         ├── AgentFindings (Diagnostic hypotheses, detected anomalies)
         │
         └── ReasoningResults (Synthesized Root Cause Analysis & Confidence)
               │
               └── RemediationPlans (Strategy, risk assessment, ordered actions)
                     │
                     ├── ApprovalRequests (HITL & Policy evaluation: approved / rejected)
                     │
                     └── Actions (Specific MCP tool invocations, execution results)
                           │
                           └── AuditLogs (Immutable audit trail of state changes and actors)
```

---

## 2. Core Entities & Schema Definitions

### 1. Production Context
- `projects`: Top-level studio production.
- `sequences`: Production sequence (e.g. `SQ020`).
- `shots`: VFX shot unit (e.g. `SH010`).
- `render_jobs`: Render farm job tracking (Deadline / Tractor / OpenCue).
- `render_nodes`: Compute blade telemetry & hardware state.

### 2. Incident & Investigation
- `incidents`: Central aggregate record of an anomaly/failure.
- `incident_evidence`: Raw/structured logs, metrics, frame digests linked to the incident.
- `agent_runs`: Individual execution record of an ADK specialist or supervisor agent (supports multiple runs per incident).
- `agent_findings`: Granular findings, diagnostics, and metrics emitted by an agent.
- `reasoning_results`: Gemini/Supervisor synthesis linking findings and evidence to root cause.

### 3. Remediation & Governance
- `remediation_plans`: Proposed multi-step remediation workflow with risk assessment.
- `approval_requests`: Human-in-the-loop and automated policy approval decisions.
- `actions`: Executable unit of work (e.g., call MCP tool `retry_job_on_healthy_node`).
- `audit_logs`: Immutable ledger tracking every change, actor, and timestamp.
