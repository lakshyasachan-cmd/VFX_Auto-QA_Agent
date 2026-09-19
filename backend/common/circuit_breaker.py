"""
Circuit Breaker Pattern for external integrations (IBM watsonx, Deadline, Tractor, ShotGrid).
Prevents cascading failures by halting requests to failing external systems,
transitioning through CLOSED, OPEN, and HALF_OPEN states.
"""

from enum import Enum
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("vfx.common.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal operations
    OPEN = "OPEN"            # Tripped; requests fail fast
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreakerOpenException(RuntimeError):
    """Raised when an operation is rejected by an OPEN circuit breaker."""
    def __init__(self, name: str, retry_after_seconds: float):
        super().__init__(f"Circuit breaker '{name}' is OPEN. Remote service unavailable. Retry after {retry_after_seconds:.1f}s.")
        self.name = name
        self.retry_after_seconds = retry_after_seconds


class CircuitBreaker:
    """
    In-memory resilience circuit breaker with configurable failure threshold,
    cooldown duration, and half-open success confirmation.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        half_open_success_threshold: int = 2,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_success_threshold = half_open_success_threshold

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_state_change = time.time()

    @property
    def state(self) -> CircuitState:
        now = time.time()
        # If OPEN and timeout elapsed, transition to HALF_OPEN
        if self._state == CircuitState.OPEN:
            if now - self._last_state_change >= self.recovery_timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        logger.info("CircuitBreaker '%s' transitioned: %s -> %s", self.name, self._state.value, new_state.value)
        self._state = new_state
        self._last_state_change = time.time()
        if new_state == CircuitState.HALF_OPEN:
            self._consecutive_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._consecutive_failures = 0
            self._consecutive_successes = 0

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute callable wrapped by circuit breaker protections."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            elapsed = time.time() - self._last_state_change
            remaining = max(0.0, self.recovery_timeout_seconds - elapsed)
            raise CircuitBreakerOpenException(self.name, remaining)

        try:
            result = fn(*args, **kwargs)
            self.on_success()
            return result
        except Exception as exc:
            self.on_failure(exc)
            raise

    def on_success(self) -> None:
        """Record successful execution."""
        if self._state == CircuitState.HALF_OPEN:
            self._consecutive_successes += 1
            if self._consecutive_successes >= self.half_open_success_threshold:
                self._transition_to(CircuitState.CLOSED)
        elif self._state == CircuitState.CLOSED:
            self._consecutive_failures = 0

    def on_failure(self, exc: Exception) -> None:
        """Record failed execution."""
        self._consecutive_failures += 1
        logger.warning("CircuitBreaker '%s' recorded failure (%d/%d): %s", self.name, self._consecutive_failures, self.failure_threshold, exc)

        if self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            if self._consecutive_failures >= self.failure_threshold or self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)


# Registry of active circuit breakers
_circuit_registry: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    recovery_timeout_seconds: float = 30.0,
) -> CircuitBreaker:
    """Get or create a named circuit breaker singleton."""
    if name not in _circuit_registry:
        _circuit_registry[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=recovery_timeout_seconds,
        )
    return _circuit_registry[name]
