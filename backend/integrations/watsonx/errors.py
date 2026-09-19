"""
Structured exception hierarchy for IBM watsonx Orchestrate Integration.
"""

from typing import Any, Optional


class WatsonxError(Exception):
    """Base exception for all watsonx Orchestrate errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "WATSONX_ERROR",
        status_code: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }


class WatsonxConfigurationError(WatsonxError):
    """Raised when required live integration configuration is missing."""

    def __init__(self, message: str, missing_keys: Optional[list[str]] = None) -> None:
        super().__init__(
            message=message,
            error_code="WATSONX_CONFIGURATION_ERROR",
            status_code=500,
            details={"missing_keys": missing_keys or []},
        )


class WatsonxAuthenticationError(WatsonxError):
    """Raised when IBM IAM or watsonx authentication fails."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(
            message=message,
            error_code="WATSONX_AUTH_ERROR",
            status_code=status_code,
        )


class WatsonxTimeoutError(WatsonxError):
    """Raised when an external request to watsonx times out."""

    def __init__(self, message: str, timeout_seconds: float) -> None:
        super().__init__(
            message=message,
            error_code="WATSONX_TIMEOUT",
            status_code=504,
            details={"timeout_seconds": timeout_seconds},
        )


class WatsonxWorkflowExecutionError(WatsonxError):
    """Raised when a watsonx workflow/skill returns an execution failure."""

    def __init__(
        self,
        message: str,
        workflow_id: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="WATSONX_WORKFLOW_EXECUTION_ERROR",
            status_code=status_code or 502,
            details={"workflow_id": workflow_id, **(details or {})},
        )
