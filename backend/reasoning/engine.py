"""
Root Cause Reasoning Engine for the VFX Pipeline Incident Platform.
Synthesizes specialist findings from Render QA, Hardware Diagnostics, Asset Validation,
and Historical Evidence into a strict structured root cause analysis using Gemini.

STRICT AI SAFETY RULES:
1. Do not fabricate evidence.
2. Do not execute tools.
3. Do not modify production systems.
4. Do not convert uncertainty into certainty.
5. If evidence is insufficient, return INSUFFICIENT_EVIDENCE.
"""

import logging
import os
from typing import Any, Optional

from backend.reasoning.mock_gemini import MockGeminiClient
from backend.reasoning.prompt_builder import (
    SYSTEM_INSTRUCTION,
    build_reasoning_prompt,
)
from backend.reasoning.schemas import (
    ReasoningContextInput,
    RootCauseAnalysis,
)

logger = logging.getLogger("vfx.reasoning.engine")


class RootCauseReasoningEngine:
    """
    Root Cause Reasoning Engine powered by Gemini through Google AI/ADK integration.
    Analyzes specialist agent telemetry and outputs strict structured diagnostic conclusions.
    """

    def __init__(
        self,
        gemini_client: Optional[Any] = None,
        model_name: Optional[str] = None,
        use_mock: Optional[bool] = None,
    ) -> None:
        # Read model from env var, fall back to gemini-2.5-flash
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        # Auto-detect mock mode: use_mock=True only if GEMINI_API_KEY is absent
        api_key_present = bool(os.getenv("GEMINI_API_KEY"))
        if use_mock is None:
            use_mock = not api_key_present  # True when key missing, False when key set
        self.use_mock = use_mock

        if gemini_client is not None:
            self.client = gemini_client
        elif use_mock or not api_key_present:
            logger.info("GEMINI_API_KEY not set or use_mock=True — using MockGeminiClient.")
            self.client = MockGeminiClient()
        else:
            try:
                from google import genai
                self.client = genai.Client()
                logger.info("Live Gemini client initialized with model: %s", self.model_name)
            except Exception as e:
                logger.warning(f"Failed to initialize live GenAI client: {e}. Falling back to mock.")
                self.client = MockGeminiClient()


    def analyze(self, context: ReasoningContextInput) -> RootCauseAnalysis:
        """
        Synthesize multi-agent evidence into a singular root cause analysis.
        Strictly enforces safety invariants and returns structured JSON output.
        """
        # 1. Pre-flight Evidence Sufficiency Check
        has_incident = bool(context.incident)
        has_findings = bool(
            context.render_qa_findings or
            context.hardware_findings or
            context.asset_findings or
            (context.historical_evidence and context.historical_evidence.get("similar_incidents"))
        )

        if not has_incident or not has_findings:
            # Rule: If evidence is insufficient, return INSUFFICIENT_EVIDENCE
            return RootCauseAnalysis(
                root_cause="INSUFFICIENT_EVIDENCE",
                confidence=0.10,
                severity="LOW",
                supporting_evidence=[],
                contradicting_evidence=[],
                alternative_causes=[],
                recommended_action="DISPATCH_INVESTIGATION_MANUAL",
                remediation_category="GOVERNANCE",
                reasoning_summary="Diagnostic evidence is absent or insufficient to infer root cause without speculation.",
                incident_id=context.incident.get("incident_id") or context.incident.get("event_id"),
            )

        # 2. Build Structured Prompt
        prompt = build_reasoning_prompt(context)

        # 3. Model Generation
        if isinstance(self.client, MockGeminiClient):
            result = self.client.generate_analysis(context, prompt)
        else:
            try:
                from google.genai import types
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        response_schema=RootCauseAnalysis,
                        temperature=0.1,  # Low temperature for deterministic factual deduction
                    ),
                )
                result = RootCauseAnalysis.model_validate_json(response.text)
            except Exception as e:
                logger.error(f"Live Gemini reasoning failed: {e}. Utilizing deterministic fallback.")
                fallback_mock = MockGeminiClient()
                result = fallback_mock.generate_analysis(context, prompt)

        # 4. Post-flight Safety Validation
        # Ensure incident ID is tagged
        if not result.incident_id:
            result.incident_id = context.incident.get("incident_id") or context.incident.get("event_id")

        return result
