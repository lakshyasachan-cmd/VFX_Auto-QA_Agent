# VFX Mission Control — Security Architecture & Production Audit Guide

This document establishes the security architecture, threat model, boundaries, access controls, and operational policies for the **VFX Mission Control** platform.

---

## 1. Security Architecture Principles

1. **Principle of Least Privilege**:
   - Specialists inspect and report; they never modify production files or execute farm actions.
   - LLMs propose actions; deterministic policy engines decide approval necessity; human supervisors or automated gates approve; governed MCP gateways execute.
2. **Untrusted LLM Isolation**:
   - Language models and generative AI (Gemini) are strictly isolated from tool execution and production infrastructure.
   - All MCP tool calls mandate verified [`MCPExecutionContext`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/mcp/schemas.py) containing a valid `approval_id`. Direct or prompt-injected LLM invocations are blocked at the gateway boundary.
3. **Deterministic Human-in-the-Loop Governance**:
   - AI recommendations cannot override studio policy rules. High-confidence suggestions can still be rejected or forced to require human approval.
4. **Zero Hardcoded Secrets**:
   - All credentials, API keys, and connection strings are managed strictly via environment variables.

---

## 2. Authentication Boundary & Role-Based Access Control (RBAC)

All external REST API endpoints are protected by the [`backend/common/auth.py`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/common/auth.py) security boundary.

### Supported Authentication Schemes
- **API Key**: `X-API-Key: <token>`
- **Bearer Token**: `Authorization: Bearer <token>`

### Roles & Access Matrix

| Role | Permitted Actions | Accessible Endpoints |
|---|---|---|
| **ADMIN** | Full administrative rights, secret rotation, system configuration | All `/api/v1/*` endpoints |
| **LEAD_TD** | Action approval/rejection, high-risk farm modifications, shot status changes | `/api/v1/approvals/*`, `/api/v1/mcp/*`, `/api/v1/events/*` |
| **TD** | Low/medium risk job retries, incident investigation, notes | `/api/v1/approvals` (read), `/api/v1/events/*`, `/api/v1/mcp/tools` |
| **ARTIST** | Read-only access to incident status and triage alerts | `/api/v1/events` (read-only), `/api/v1/mcp/tools` |
| **SYSTEM** | Automated ingestion pipelines, supervisor agents, watsonx orchestrate | Ingestion, MCP execution with context |

---

## 3. Threat Analysis & Vulnerability Mitigations

### 3.1 Prompt Injection Risks
- **Threat**: Malicious log contents or craftily named asset paths containing prompt injection payloads attempting to trick Gemini into recommending destructive actions or exfiltrating data.
- **Mitigation**:
  1. Strict system prompt boundary in [`SYSTEM_INSTRUCTION`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/reasoning/prompt_builder.py).
  2. Gemini only outputs strict JSON adhering to [`RootCauseAnalysis`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/reasoning/schemas.py).
  3. Even if Gemini recommends a destructive action (e.g. `DROP_DATABASE`), the deterministic [`PolicyEngine`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/governance/policy_engine.py) immediately intercepts and classifies it as `POLICY_REJECT` (`is_blocked=True`).

### 3.2 Unauthorized Tool Execution & Insecure MCP Tools
- **Threat**: An unauthorized user or autonomous agent invoking MCP tools directly against render nodes or storage.
- **Mitigation**:
  1. [`MCPExecutionGateway`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/mcp/gateway.py) verifies:
     - Context presence (`context` is non-null).
     - Caller authorization (`actor` is authenticated and not unprivileged).
     - Valid approval (`approval_id` exists with status `APPROVED` or `AUTO_APPROVED`).
     - Action identity (`tool_name` matches approved `action_name`).
     - Replay prevention (`approval_id` cannot be executed more than once).
     - Strict Pydantic parameter schema validation.

### 3.3 Server-Side Request Forgery (SSRF)
- **Threat**: Target URLs in webhook ingestion or watsonx integration redirected to internal cloud metadata (`http://169.254.169.254`).
- **Mitigation**:
  - `WATSONX_INSTANCE_URL` and `IAM_TOKEN_URL` are strictly validated and configurable solely by trusted system administrators through environment variables.
  - User-submitted events do not trigger dynamic outbound HTTP calls to caller-provided URLs.

### 3.4 Command Injection & Arbitrary Shell Execution
- **Threat**: Executing shell commands using unescaped parameters from render logs or job IDs.
- **Mitigation**:
  - Zero usage of `os.system()`, `subprocess.Popen(..., shell=True)`, or `eval()` across the entire codebase.
  - All farm integrations interact via structured Python APIs or controlled HTTP REST contracts.

### 3.5 Arbitrary File Access & Directory Traversal
- **Threat**: Asset validation accessing arbitrary paths outside studio storage mounts.
- **Mitigation**:
  - Asset path queries use canonical repository catalogs and sanitized paths without path concatenation or traversal vulnerability.
  - Read-only inspection guarantees files are never modified or created outside controlled boundaries.

### 3.6 SQL Injection
- **Threat**: Malicious parameters injected into database queries.
- **Mitigation**:
  - All database interactions strictly use SQLAlchemy 2.0 object-relational models and parameterized queries (`mapped_column`, `session.query()`, `select()`). Raw unescaped SQL strings are forbidden.

---

## 4. Secret Management & Sensitive Data Sanitization

1. **Environment Variable Configuration**:
   - `WATSONX_API_KEY`: IBM Cloud IAM API Key
   - `WATSONX_INSTANCE_URL`: IBM watsonx Orchestrate instance URL
   - `GEMINI_API_KEY`: Google Cloud Gemini API key
   - `DATABASE_URL`: PostgreSQL / SQLite connection string
   - `REDIS_URL`: Redis Stream bus connection string
   - `VFX_ADMIN_API_KEY`, `VFX_LEAD_TD_API_KEY`, `VFX_TD_API_KEY`: Service API keys
2. **Strict Sanitization Policy**:
   - In [`backend/common/logging.py`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/common/logging.py), all logs pass through `sanitize_sensitive_data()`.
   - Keys such as `api_key`, `password`, `token`, `secret`, `authorization`, and Bearer headers are recursively replaced with `[REDACTED]`.
   - Raw secrets are never written to disk, audit logs, or error responses.

---

## 5. Rate Limiting & Denial of Service Protection

- Implemented in [`backend/common/rate_limit.py`](file:///c:/Users/Lakshya/OneDrive/Desktop/New%20folder/backend/common/rate_limit.py).
- Uses a sliding window algorithm (default 120 requests/minute per client IP / API key).
- Excess requests receive `HTTP 429 Too Many Requests` with a `Retry-After` header.
