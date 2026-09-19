"""
Google ADK Supervisor Agent for the VFX Incident Platform.
Coordinates specialist agents, detects conflicts, aggregates evidence, and produces structured investigation results.
STRICT RULE: The supervisor MUST NOT directly execute production actions.
"""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Optional
from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event

from backend.agents.supervisor.classifier import IncidentClassifier
from backend.agents.supervisor.conflict_detector import ConflictDetector
from backend.agents.supervisor.mock_specialists import (
    MockAssetValidationAgent,
    MockHardwareDiagnosticAgent,
    MockHistoricalEvidenceAgent,
    MockRenderQAAgent,
)
from backend.agents.supervisor.schemas import (
    AgentExecutionTrace,
    AgentFindingDTO,
    EvidenceItemDTO,
    InvestigationRequest,
    InvestigationResult,
    InvestigationStatus,
    SpecialistReport,
)

logger = logging.getLogger("vfx.agents.supervisor")


class SupervisorAgent(BaseAgent):
    """
    Root Multi-Agent Supervisor built on Google ADK.
    Dynamically routes incident investigations to specialist sub-agents.
    """

    name: str = "IncidentSupervisor"
    description: str = (
        "Multi-agent supervisor responsible for classifying VFX incidents, "
        "delegating investigations to domain specialists, resolving conflicts, "
        "and compiling root-cause diagnostic reports."
    )

    # Internal sub-components (excluded from Pydantic fields via model_config or non-field attrs)
    classifier: IncidentClassifier = None  # type: ignore
    conflict_detector: ConflictDetector = None  # type: ignore

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.classifier is None:
            self.classifier = IncidentClassifier()
        if self.conflict_detector is None:
            self.conflict_detector = ConflictDetector()

        # If sub_agents were not explicitly provided, register default specialists
        if not self.sub_agents:
            self.sub_agents = [
                MockRenderQAAgent(),
                MockHardwareDiagnosticAgent(),
                MockAssetValidationAgent(),
                MockHistoricalEvidenceAgent(),
            ]

    def _get_specialist(self, agent_name: str) -> Optional[BaseAgent]:
        """Lookup a registered sub-agent by name."""
        for agent in self.sub_agents:
            if agent.name == agent_name:
                return agent
        return None

    async def _execute_specialist_safely(
        self,
        specialist: BaseAgent,
        incident_id: str,
        event: dict[str, Any],
        timeout_seconds: float,
    ) -> tuple[SpecialistReport, AgentExecutionTrace]:
        """
        Executes an individual specialist with timeout and exception containment.
        Fails safely if the specialist throws an unhandled error.
        """
        start_time = time.perf_counter()
        trace = AgentExecutionTrace(agent_name=specialist.name, status="SUCCESS")

        try:
            # Call specialist investigate method with strict timeout
            if hasattr(specialist, "investigate"):
                report = await asyncio.wait_for(
                    specialist.investigate(incident_id, event),
                    timeout=timeout_seconds,
                )
            else:
                raise AttributeError(f"Specialist '{specialist.name}' does not implement 'investigate'")

            trace.duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            trace.status = "SUCCESS"
            return report, trace

        except asyncio.TimeoutError:
            duration = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning("Specialist '%s' timed out after %s seconds", specialist.name, timeout_seconds)
            trace.duration_ms = duration
            trace.status = "TIMED_OUT"
            trace.error = f"Execution timed out after {timeout_seconds}s"
            return (
                SpecialistReport(
                    agent_name=specialist.name,
                    status="TIMED_OUT",
                    error_message=trace.error,
                ),
                trace,
            )

        except Exception as exc:
            duration = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error("Specialist '%s' failed: %s", specialist.name, exc)
            trace.duration_ms = duration
            trace.status = "FAILED"
            trace.error = str(exc)
            return (
                SpecialistReport(
                    agent_name=specialist.name,
                    status="FAILED",
                    error_message=trace.error,
                ),
                trace,
            )

    async def investigate_incident(
        self,
        request: InvestigationRequest | dict[str, Any],
    ) -> InvestigationResult:
        """
        Primary investigation orchestrator:
        1. Understands incident and extracts context
        2. Classifies incident type
        3. Selects relevant specialist agents
        4. Concurrently delegates investigation to specialists
        5. Collects specialist findings and evidence
        6. Detects conflicting findings across specialists
        7. Compiles evidence for reasoning layer
        8. Produces structured InvestigationResult
        """
        if isinstance(request, dict):
            req = InvestigationRequest.model_validate(request)
        else:
            req = request

        # 1 & 2 & 3. Classify and determine required specialists
        classification_report = self.classifier.classify_and_route(
            event=req.event,
            required_specialists=req.required_specialists,
        )

        selected_specialists = classification_report.selected_specialists
        missing_data_warnings = list(classification_report.missing_data_warnings)

        # 4. Delegate to selected specialists concurrently
        dispatch_tasks = []
        unavailable_agents: list[AgentExecutionTrace] = []

        for agent_name in selected_specialists:
            specialist = self._get_specialist(agent_name)
            if specialist is None:
                # Handle unavailable specialist safely
                logger.warning("Requested specialist '%s' is not registered on supervisor", agent_name)
                unavailable_agents.append(
                    AgentExecutionTrace(
                        agent_name=agent_name,
                        status="FAILED",
                        error=f"Specialist '{agent_name}' is unavailable/not registered",
                    )
                )
            else:
                dispatch_tasks.append(
                    self._execute_specialist_safely(
                        specialist=specialist,
                        incident_id=req.incident_id,
                        event=req.event,
                        timeout_seconds=req.timeout_seconds,
                    )
                )

        # Execute all available specialists in parallel
        results: list[tuple[SpecialistReport, AgentExecutionTrace]] = []
        if dispatch_tasks:
            results = await asyncio.gather(*dispatch_tasks)

        # 5. Collect findings, evidence, hypotheses, and traces
        all_findings: list[AgentFindingDTO] = []
        all_evidence: list[EvidenceItemDTO] = []
        all_hypotheses: list[dict[str, Any]] = []
        all_traces: list[AgentExecutionTrace] = list(unavailable_agents)

        success_count = 0
        failure_count = len(unavailable_agents)

        for report, trace in results:
            all_traces.append(trace)
            if report.status == "SUCCESS":
                success_count += 1
                all_findings.extend(report.findings)
                all_evidence.extend(report.evidence)
                all_hypotheses.extend(report.hypotheses)
            else:
                failure_count += 1

        # Determine overall investigation status
        if success_count > 0 and failure_count == 0:
            status = InvestigationStatus.INVESTIGATION_COMPLETE
        elif success_count > 0 and failure_count > 0:
            status = InvestigationStatus.PARTIAL_INVESTIGATION
        else:
            status = InvestigationStatus.INVESTIGATION_FAILED

        # 6. Detect Conflicting Findings
        conflicts = self.conflict_detector.detect_conflicts(
            findings=all_findings,
            hypotheses=all_hypotheses,
        )

        # 7 & 8. Calculate aggregate confidence and synthesize summary
        if all_findings:
            # Baseline: average of top finding confidences
            top_confidences = sorted([f.confidence for f in all_findings], reverse=True)[:3]
            base_confidence = sum(top_confidences) / len(top_confidences)
        else:
            base_confidence = 0.1 if status == InvestigationStatus.PARTIAL_INVESTIGATION else 0.0

        # Adjust confidence downwards if conflicts exist
        if conflicts:
            confidence_penalty = 0.2 if any(c.severity == "HIGH" for c in conflicts) else 0.1
            base_confidence = max(0.1, base_confidence - confidence_penalty)

        # Penalize for missing critical data
        if missing_data_warnings:
            base_confidence = max(0.1, base_confidence - (0.05 * len(missing_data_warnings)))

        final_confidence = round(min(1.0, max(0.0, base_confidence)), 2)

        # Determine best root cause hypothesis
        root_cause_hypothesis = None
        if all_findings:
            # Pick highest confidence finding
            highest_finding = max(all_findings, key=lambda f: f.confidence)
            root_cause_hypothesis = highest_finding.title
        elif status == InvestigationStatus.INVESTIGATION_FAILED:
            root_cause_hypothesis = "Unable to determine root cause: all specialist agents failed or timed out"

        # Generate summary
        summary_parts = [
            f"Classified incident as '{classification_report.classification.value}'.",
            f"Delegated to {len(selected_specialists)} specialists ({success_count} succeeded, {failure_count} failed).",
        ]
        if conflicts:
            summary_parts.append(f"WARNING: Detected {len(conflicts)} conflicting finding(s) among specialists.")
        if missing_data_warnings:
            summary_parts.append(f"Noted {len(missing_data_warnings)} missing data warning(s).")
        if root_cause_hypothesis:
            summary_parts.append(f"Primary diagnostic hypothesis: {root_cause_hypothesis} (Confidence: {final_confidence}).")

        summary = " ".join(summary_parts)

        return InvestigationResult(
            incident_id=req.incident_id,
            incident_type=classification_report.classification,
            selected_specialists=selected_specialists,
            findings=all_findings,
            evidence=all_evidence,
            conflicts=conflicts,
            confidence=final_confidence,
            status=status,
            summary=summary,
            agent_traces=all_traces,
            root_cause_hypothesis=root_cause_hypothesis,
            missing_data_warnings=missing_data_warnings,
        )

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Google ADK runtime execution implementation.
        """
        yield Event(author=self.name, content={"status": "SUPERVISOR_RUNNING"})

        user_content = getattr(ctx, "user_content", None) or {}
        incident_id = user_content.get("incident_id", "incident-adk-001")

        result = await self.investigate_incident({
            "incident_id": incident_id,
            "event": user_content.get("event", {}),
        })

        yield Event(
            author=self.name,
            content=result.model_dump(mode="json"),
            turn_complete=True,
        )
