"""
Deterministic Risk Policy Engine for VFX Remediation Strategies.
Enforces hard deterministic policy rules for risk classification and human-in-the-loop approval.
STRICT RULE: LLM recommendations must NEVER bypass deterministic policy rules.
"""

from typing import Any, Optional
from backend.remediation.schemas import (
    ActionType,
    RemediationActionProposal,
    RiskLevel,
)

RISK_ORDER = {
    RiskLevel.LOW.value: 1,
    RiskLevel.MEDIUM.value: 2,
    RiskLevel.HIGH.value: 3,
    RiskLevel.CRITICAL.value: 4,
}


def compare_risk(r1: str, r2: str) -> str:
    """Return the higher risk level between r1 and r2."""
    v1 = RISK_ORDER.get(r1.upper(), 1)
    v2 = RISK_ORDER.get(r2.upper(), 1)
    return r1 if v1 >= v2 else r2


class DeterministicRiskPolicyEngine:
    """
    Deterministic governance engine that validates and enforces risk tiers and
    human-in-the-loop approval requirements. LLMs cannot weaken these constraints.
    """

    def evaluate_action(
        self,
        action: str,
        parameters: dict[str, Any],
        confidence: float,
        incident_severity: str,
        reason: str = "",
        llm_suggested_risk: Optional[str] = None,
        llm_suggested_approval: Optional[bool] = None,
    ) -> tuple[RemediationActionProposal, list[str]]:
        """
        Evaluate and enforce deterministic policy rules on a proposed action.
        Returns the finalized RemediationActionProposal and policy evaluation logs.
        """
        logs: list[str] = []
        action_name = action.upper()
        severity = incident_severity.upper()

        # 1. Determine baseline risk according to deterministic rulebook
        if action_name in (ActionType.NO_ACTION.value, ActionType.NOTIFY_TEAM.value, ActionType.GENERATE_POSTMORTEM.value, ActionType.CREATE_INCIDENT.value):
            base_risk = RiskLevel.LOW.value
            needs_approval = False
            logs.append(f"Policy: Action '{action_name}' is read-only/informational -> baseline LOW risk.")

        elif action_name in (ActionType.ASSIGN_PIPELINE_TD.value, ActionType.UPDATE_SHOT_STATUS.value):
            base_risk = RiskLevel.MEDIUM.value
            # If severity is CRITICAL or status change is disruptive, require approval
            target_status = str(parameters.get("status", "")).upper()
            if severity == "CRITICAL" or target_status in ("FINAL", "APPROVED", "OMIT"):
                needs_approval = True
                logs.append(f"Policy: '{action_name}' on CRITICAL incident or disruptive status '{target_status}' -> requires human approval.")
            else:
                needs_approval = False
                logs.append(f"Policy: Action '{action_name}' baseline MEDIUM risk (auto-approvable status transition).")

        elif action_name == ActionType.RETRY_JOB.value:
            # Farm job retry rules
            target_pool = str(parameters.get("target_pool", "")).lower()
            is_high_resource = any(k in target_pool for k in ["80gb", "cloud", "burst", "a100", "h100", "highmem"])
            has_modifications = bool(parameters.get("parameter_overrides") or parameters.get("downscale"))

            if is_high_resource or has_modifications:
                base_risk = RiskLevel.HIGH.value
                needs_approval = True
                logs.append(f"Policy: RETRY_JOB requesting high-resource pool '{target_pool}' or parameter overrides -> strictly HIGH risk, requires approval.")
            else:
                base_risk = RiskLevel.MEDIUM.value
                needs_approval = (confidence < 0.90 or severity in ("HIGH", "CRITICAL"))
                logs.append(f"Policy: Standard RETRY_JOB -> MEDIUM risk (approval required: {needs_approval}).")

        else:
            # Unrecognized custom action defaults to HIGH risk
            base_risk = RiskLevel.HIGH.value
            needs_approval = True
            logs.append(f"Policy: Unrecognized action '{action_name}' -> conservatively classified as HIGH risk, requires approval.")

        # 2. Check for destructive/reboot parameters
        param_str = str(parameters).lower()
        if any(k in param_str for k in ["reboot", "delete", "purge_all", "kill_process", "drop"]):
            base_risk = RiskLevel.CRITICAL.value
            needs_approval = True
            logs.append("Policy ESCALATION: Destructive operations detected in parameters -> escalated to CRITICAL risk.")

        # 3. Escalation based on Low Confidence (< 0.75)
        if confidence < 0.75 and base_risk != RiskLevel.LOW.value:
            base_risk = compare_risk(base_risk, RiskLevel.HIGH.value)
            needs_approval = True
            logs.append(f"Policy ESCALATION: Confidence {confidence:.2f} < 0.75 -> escalated to HIGH risk with mandatory human approval.")

        # 4. Mandatory Rule: HIGH and CRITICAL risk ALWAYS require human approval
        if base_risk in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value):
            needs_approval = True

        # 5. Overrule LLM attempts to bypass deterministic policy
        if llm_suggested_risk and RISK_ORDER.get(llm_suggested_risk.upper(), 1) < RISK_ORDER.get(base_risk, 1):
            logs.append(f"Policy OVERRIDE: LLM suggested risk '{llm_suggested_risk}' bypassed; strictly enforced deterministic risk '{base_risk}'.")

        if llm_suggested_approval is False and needs_approval is True:
            logs.append("Policy OVERRIDE: LLM suggested requires_human_approval=False bypassed; strictly enforced human review.")

        proposal = RemediationActionProposal(
            action=action_name,
            reason=reason,
            risk=base_risk,
            confidence=round(confidence, 3),
            requires_human_approval=needs_approval,
            parameters=parameters,
        )

        return proposal, logs

    def calculate_overall_plan_risk(
        self,
        actions: list[RemediationActionProposal],
    ) -> tuple[str, bool]:
        """Determine overall plan risk (highest action risk) and aggregate approval requirement."""
        if not actions:
            return RiskLevel.LOW.value, False

        highest_risk = RiskLevel.LOW.value
        requires_approval = False

        for a in actions:
            highest_risk = compare_risk(highest_risk, a.risk)
            if a.requires_human_approval:
                requires_approval = True

        return highest_risk, requires_approval
