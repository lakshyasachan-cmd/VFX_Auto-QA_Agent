"""
Base contract for specialist agents compatible with Google ADK.
"""

from abc import abstractmethod
from typing import Any, AsyncGenerator
from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event

from backend.agents.supervisor.schemas import SpecialistReport


class BaseSpecialistAgent(BaseAgent):
    """
    Abstract specialist agent subclassing Google ADK BaseAgent.
    Provides uniform investigation interface and ADK event generation.
    """

    # Test simulation hooks
    should_fail: bool = False
    delay_seconds: float = 0.0
    failure_message: str = "Simulated agent failure"

    @abstractmethod
    async def investigate(self, incident_id: str, event: dict[str, Any]) -> SpecialistReport:
        """Execute domain-specific diagnostic investigation."""
        pass

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Google ADK execution runtime hook."""
        # Yield ADK lifecycle events
        yield Event(author=self.name, content={"status": "INVESTIGATION_STARTED"})
        try:
            report = await self.investigate("ctx-incident", {})
            yield Event(
                author=self.name,
                content=report.model_dump(mode="json"),
                turn_complete=True,
            )
        except Exception as e:
            yield Event(
                author=self.name,
                error_code="SPECIALIST_ERROR",
                error_message=str(e),
                turn_complete=True,
            )
