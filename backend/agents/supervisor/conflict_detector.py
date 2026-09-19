"""
Conflict detection engine for multi-agent findings.
Analyzes hypotheses and assertions across specialists to identify contradictions.
"""

from typing import Any
from backend.agents.supervisor.schemas import AgentFindingDTO, ConflictItem


class ConflictDetector:
    """
    Detects contradictions between specialist findings (e.g., Software vs. Hardware blame).
    """

    def detect_conflicts(
        self,
        findings: list[AgentFindingDTO],
        hypotheses: list[dict[str, Any]],
    ) -> list[ConflictItem]:
        """
        Scan all findings and hypotheses for opposing conclusions.
        Returns a list of ConflictItems.
        """
        conflicts: list[ConflictItem] = []

        # Categorize high-confidence findings by agent and domain
        hardware_findings = [f for f in findings if f.category == "hardware" and f.confidence >= 0.7]
        software_findings = [f for f in findings if f.category == "software" and f.confidence >= 0.7]

        # 1. Contradiction: Software Shader/Scene Crash vs. Node Hardware Failure
        if hardware_findings and software_findings:
            hw_agent = hardware_findings[0].agent_name
            sw_agent = software_findings[0].agent_name
            if hw_agent != sw_agent:
                conflicts.append(
                    ConflictItem(
                        conflicting_agents=[hw_agent, sw_agent],
                        reason=(
                            f"Contradictory Root Cause: '{sw_agent}' blames software/scene error "
                            f"({software_findings[0].title}), whereas '{hw_agent}' attributes failure "
                            f"to compute hardware breakdown ({hardware_findings[0].title})."
                        ),
                        hypothesis_a={
                            "agent": sw_agent,
                            "assertion": software_findings[0].title,
                            "confidence": software_findings[0].confidence,
                        },
                        hypothesis_b={
                            "agent": hw_agent,
                            "assertion": hardware_findings[0].title,
                            "confidence": hardware_findings[0].confidence,
                        },
                        severity="HIGH",
                    )
                )

        # 2. Contradiction: Asset Valid vs. Render Missing Asset
        # Look for hypotheses claiming asset is valid vs. asset missing
        asset_valid_claims = [
            f for f in findings
            if f.category == "asset" and "VALID" in f.finding_type.upper() and f.confidence >= 0.7
        ]
        render_asset_missing_claims = [
            f for f in findings
            if f.category == "software" and any(k in f.title.upper() for k in ["MISSING", "NOT FOUND", "ASSET_LOAD_ERROR"])
        ]
        if asset_valid_claims and render_asset_missing_claims:
            conflicts.append(
                ConflictItem(
                    conflicting_agents=[asset_valid_claims[0].agent_name, render_asset_missing_claims[0].agent_name],
                    reason=(
                        f"Asset State Disagreement: '{asset_valid_claims[0].agent_name}' asserts asset is valid, "
                        f"but '{render_asset_missing_claims[0].agent_name}' reports asset cannot be found."
                    ),
                    hypothesis_a={
                        "agent": asset_valid_claims[0].agent_name,
                        "assertion": asset_valid_claims[0].title,
                        "confidence": asset_valid_claims[0].confidence,
                    },
                    hypothesis_b={
                        "agent": render_asset_missing_claims[0].agent_name,
                        "assertion": render_asset_missing_claims[0].title,
                        "confidence": render_asset_missing_claims[0].confidence,
                    },
                    severity="MEDIUM",
                )
            )

        # 3. Check explicit conflicting hypotheses if supplied in agent reports
        for i, hyp_a in enumerate(hypotheses):
            for hyp_b in hypotheses[i + 1:]:
                if (
                    hyp_a.get("agent_name") != hyp_b.get("agent_name")
                    and hyp_a.get("claim_type") == "opposing"
                    and hyp_b.get("claim_type") == "opposing"
                ):
                    conflicts.append(
                        ConflictItem(
                            conflicting_agents=[hyp_a.get("agent_name", "Unknown"), hyp_b.get("agent_name", "Unknown")],
                            reason=f"Direct hypothesis clash: {hyp_a.get('hypothesis')} vs {hyp_b.get('hypothesis')}",
                            hypothesis_a=hyp_a,
                            hypothesis_b=hyp_b,
                            severity="HIGH",
                        )
                    )

        return conflicts
