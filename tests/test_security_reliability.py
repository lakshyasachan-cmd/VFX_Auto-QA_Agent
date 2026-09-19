"""
Comprehensive Test Suite for Security, Reliability & Observability.
Covers:
1. Structured JSON logging & credential sanitization (passwords, tokens, API keys)
2. Trace context propagation (incident_id, correlation_id, agent_run_id, mcp_execution_id)
3. API authentication boundary (API keys and Bearer tokens)
4. Role-based access control (RBAC: ADMIN, LEAD_TD, TD)
5. Circuit breaker pattern states (CLOSED, OPEN, HALF_OPEN)
6. Sliding window rate limiting
7. Database transaction boundaries and rollback safety
"""

import json
import logging
import pytest
from unittest.mock import MagicMock

from backend.common.auth import (
    AuthenticatedUser,
    UserRole,
    authenticate_request,
    get_configured_api_keys,
    require_role,
)
from backend.common.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    CircuitState,
)
from backend.common.logging import (
    StructuredJsonFormatter,
    approval_id_ctx,
    correlation_id_ctx,
    event_id_ctx,
    incident_id_ctx,
    mcp_execution_id_ctx,
    reasoning_id_ctx,
    remediation_id_ctx,
    sanitize_sensitive_data,
)
from backend.common.rate_limit import SlidingWindowRateLimiter
from backend.common.transaction import db_transaction


# ==============================================================================
# 1. Structured JSON Logging & Credential Sanitization Tests
# ==============================================================================

def test_credential_sanitization_patterns():
    """Verify that passwords, API keys, and bearer tokens are strictly redacted."""
    raw_dict = {
        "user": "alex",
        "api_key": "secret_vfx_key_999",
        "nested": {
            "password": "super_secret_password",
            "token": "ghp_1234567890",
            "safe_field": "node-blade-01",
        },
    }
    sanitized = sanitize_sensitive_data(raw_dict)
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == "node-blade-01"

    # Test string pattern redaction
    raw_str = "Connecting with Authorization: Bearer eyJhbGciOiJIUzI1Ni... and api_key='secret-key-123'"
    sanitized_str = sanitize_sensitive_data(raw_str)
    assert "Bearer" in sanitized_str
    assert "secret-key-123" not in sanitized_str


def test_structured_json_formatter_trace_context():
    """Verify formatter embeds trace context variables cleanly."""
    formatter = StructuredJsonFormatter()
    correlation_id_ctx.set("corr-test-01")
    incident_id_ctx.set("inc-test-01")
    mcp_execution_id_ctx.set("exec-test-01")

    record = logging.LogRecord(
        name="vfx.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Execution completed with api_key=secret_key",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "vfx.test"
    assert parsed["trace_context"]["correlation_id"] == "corr-test-01"
    assert parsed["trace_context"]["incident_id"] == "inc-test-01"
    assert parsed["trace_context"]["mcp_execution_id"] == "exec-test-01"
    assert "secret_key" not in parsed["message"]


# ==============================================================================
# 2. Authentication Boundary & RBAC Tests
# ==============================================================================

def test_api_key_authentication():
    """Verify valid and invalid API key authentications."""
    keys = get_configured_api_keys()
    admin_key = next(k for k, u in keys.items() if u.role == UserRole.ADMIN)

    # Valid key
    user = authenticate_request(api_key=admin_key, bearer=None)
    assert user.role == UserRole.ADMIN
    assert user.username == "admin_director"

    # Invalid key
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(api_key="invalid_fake_key", bearer=None)
    assert exc_info.value.status_code == 401


def test_rbac_role_enforcement():
    """Verify that require_role grants or denies access based on permission matrix."""
    from fastapi import HTTPException

    lead_td_user = AuthenticatedUser(user_id="u1", username="lead_td", role=UserRole.LEAD_TD)
    standard_td_user = AuthenticatedUser(user_id="u2", username="artist_td", role=UserRole.TD)

    # Checker permitting ADMIN or LEAD_TD
    approval_guard = require_role([UserRole.ADMIN, UserRole.LEAD_TD])

    # Lead TD allowed
    passed = approval_guard(user=lead_td_user)
    assert passed.role == UserRole.LEAD_TD

    # Standard TD denied
    with pytest.raises(HTTPException) as exc_info:
        approval_guard(user=standard_td_user)
    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.detail


# ==============================================================================
# 3. Circuit Breaker Pattern Tests
# ==============================================================================

def test_circuit_breaker_transitions():
    """Verify circuit breaker trips to OPEN on consecutive failures and recovers."""
    breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=2,
        recovery_timeout_seconds=0.1,
        half_open_success_threshold=1,
    )
    assert breaker.state == CircuitState.CLOSED

    # Fail 1
    with pytest.raises(ValueError):
        breaker.call(MagicMock(side_effect=ValueError("Service error 1")))
    assert breaker.state == CircuitState.CLOSED

    # Fail 2 (Threshold reached -> Trips to OPEN)
    with pytest.raises(ValueError):
        breaker.call(MagicMock(side_effect=ValueError("Service error 2")))
    assert breaker.state == CircuitState.OPEN

    # In OPEN state, calls fail fast with CircuitBreakerOpenException
    with pytest.raises(CircuitBreakerOpenException):
        breaker.call(lambda: "should not be called")

    # Wait for recovery timeout
    import time
    time.sleep(0.12)
    assert breaker.state == CircuitState.HALF_OPEN

    # Successful call in HALF_OPEN recovers to CLOSED
    success_mock = MagicMock(return_value="recovered")
    res = breaker.call(success_mock)
    assert res == "recovered"
    assert breaker.state == CircuitState.CLOSED


# ==============================================================================
# 4. Sliding Window Rate Limiting Tests
# ==============================================================================

def test_sliding_window_rate_limiter():
    """Verify sliding window rate limiter permits within quota and blocks when exceeded."""
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=1.0)
    client_ip = "192.168.1.100"

    # Request 1, 2, 3 allowed
    for _ in range(3):
        allowed, remaining, _ = limiter.is_allowed(client_ip)
        assert allowed is True

    # Request 4 blocked
    allowed, remaining, reset_after = limiter.is_allowed(client_ip)
    assert allowed is False
    assert remaining == 0
    assert reset_after > 0


# ==============================================================================
# 5. Database Transaction Boundary Tests
# ==============================================================================

def test_db_transaction_rollback_on_exception():
    """Verify db_transaction rolls back and does not commit on error."""
    from backend.database.models.audit import AuditLog

    with pytest.raises(RuntimeError, match="Simulated worker abort"):
        with db_transaction() as session:
            entry = AuditLog(
                entity_type="TestRollback",
                entity_id="test-id-01",
                action="TEST_ABORT",
                actor="test_runner",
            )
            session.add(entry)
            raise RuntimeError("Simulated worker abort")

    # Verify record was not committed
    with db_transaction() as session:
        queried = session.query(AuditLog).filter_by(entity_id="test-id-01").first()
        assert queried is None
