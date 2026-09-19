# VFX Agent Contracts & Persistence Interfaces

## 1. Agent Persistence Contracts

When agents (Supervisor, Render QA, Hardware Diagnostic, Asset Validation, Historical Evidence, Remediation Strategy) execute:
1. An `AgentRun` is recorded upon initialization (`status="running"`).
2. Gathered evidence is stored in `IncidentEvidence`.
3. Agent outputs are recorded as `AgentFindings`.
4. The Reasoning Engine / Supervisor records a `ReasoningResult` linking back to the `Incident` and `AgentRun`.
5. The Remediation Agent proposes a `RemediationPlan` linked to the `ReasoningResult`.
6. Governance records an `ApprovalRequest` linked to the `RemediationPlan`.
7. Each step in the plan becomes an `Action` linked to the `RemediationPlan`.
8. Every state transition writes an `AuditLog` entry.

## 2. Decoupling Rules
- Database models contain **no business logic** or agent execution code.
- Repositories provide pure CRUD, filtering, pagination, and relational querying.
- Pydantic models serve as clean Data Transfer Objects (DTOs) for API boundaries.
