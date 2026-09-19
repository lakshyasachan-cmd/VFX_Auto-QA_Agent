"""
Structured JSON Logging for VFX Mission Control.
Provides JSON formatting, correlation/incident tracing contexts,
and strict credential sanitization (never logs API keys, passwords, tokens).
"""

import contextvars
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Optional

# Context variables for distributed tracing across operations
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)
incident_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("incident_id", default=None)
event_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("event_id", default=None)
agent_run_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("agent_run_id", default=None)
reasoning_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("reasoning_id", default=None)
remediation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("remediation_id", default=None)
approval_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("approval_id", default=None)
mcp_execution_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("mcp_execution_id", default=None)

# Regular expressions matching credential assignments
SENSITIVE_PATTERNS = [
    re.compile(r"(api[-_]?key|password|token|secret|authorization|bearer)\s*[:=]\s*([\'\"][^\'\"]+[\'\"]|[^\s,;]+)", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE),
]

SENSITIVE_KEYS = {
    "api_key", "apikey", "password", "token", "auth_token", "access_token",
    "secret", "client_secret", "watsonx_api_key", "gemini_api_key", "authorization",
    "credentials", "pwd"
}


def sanitize_sensitive_data(val: Any) -> Any:
    """Recursively redact sensitive keys and credential patterns from dictionaries or strings."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if str(k).lower() in SENSITIVE_KEYS:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_sensitive_data(v)
        return sanitized
    elif isinstance(val, (list, tuple)):
        return [sanitize_sensitive_data(x) for x in val]
    elif isinstance(val, str):
        cleaned = val
        # 1. Redact Authorization Bearer tokens preserving the 'Bearer' prefix
        cleaned = re.sub(
            r"(authorization\s*[:=]\s*)?bearer\s+[a-zA-Z0-9_\-\.]+",
            r"\1Bearer [REDACTED]",
            cleaned,
            flags=re.IGNORECASE,
        )
        # 2. Redact other key=value credential patterns
        cleaned = re.sub(
            r"(api[-_]?key|password|token|secret|credentials|pwd)\s*[:=]\s*([\'\"][^\'\"]+[\'\"]|[^\s,;]+)",
            r"\1=[REDACTED]",
            cleaned,
            flags=re.IGNORECASE,
        )
        # 3. Redact non-Bearer authorization headers
        cleaned = re.sub(
            r"authorization\s*[:=]\s*(?!Bearer\s+\[REDACTED\])([\'\"][^\'\"]+[\'\"]|[^\s,;]+)",
            r"authorization=[REDACTED]",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned
    return val


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as strict structured JSON with trace lineage and sanitized payloads."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_sensitive_data(record.getMessage()),
            "trace_context": {
                "correlation_id": correlation_id_ctx.get(),
                "incident_id": incident_id_ctx.get(),
                "event_id": event_id_ctx.get(),
                "agent_run_id": agent_run_id_ctx.get(),
                "reasoning_id": reasoning_id_ctx.get(),
                "remediation_id": remediation_id_ctx.get(),
                "approval_id": approval_id_ctx.get(),
                "mcp_execution_id": mcp_execution_id_ctx.get(),
            },
        }

        # Filter out empty trace entries
        log_data["trace_context"] = {k: v for k, v in log_data["trace_context"].items() if v is not None}

        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_data["extra"] = sanitize_sensitive_data(record.extra_data)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    """Configure root logging handler."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
