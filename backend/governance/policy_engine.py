"""
Deterministic Policy Engine for AI Governance in VFX Pipelines.
Implements the deterministic flow:
Remediation Proposal -> Policy Engine -> Risk Classification -> Auto Approval OR Human Approval -> Approved Action.

STRICT INVARIANTS:
1. The LLM CANNOT override the policy engine.
2. A high-confidence AI recommendation can still be rejected by policy.
3. Every evaluated action is deterministically bound to a rule and justification.
"""

from typing import Any, Optional
from backend.governance.schemas import (
    GovernanceDecision,
    PolicyEvaluationResult,
)

FORBIDDEN_ACTIONS = {
    "DELETE_DATABASE",
    "DROP_DATABASE",
    "PURGE_PRODUCTION_STORAGE",
    "FORCE_KILL_CLUSTER",
    "EXECUTE_ARBITRARY_SCRIPT",
    "MODIFY_SYSTEM_PERMISSIONS",
    "DROP_TABLES",
}


class PolicyEngine:
    """Deterministic governance policy evaluator."""

    def evaluate_policy(
        self,
        action: Any,
        parameters: Optional[dict[str, Any]] = None,
        confidence: float = 1.0,
        risk: Optional[str] = None,
        incident_severity: str = "MEDIUM",
        ai_recommendation_override_attempt: Optional[str] = None,
    ) -> PolicyEvaluationResult:
        """
        Evaluate proposed action against deterministic studio policies.
        Determines:
        - Risk level: LOW, MEDIUM, HIGH, CRITICAL
        - Decision: AUTO_APPROVE, HUMAN_APPROVAL, POLICY_REJECT
        """
        if isinstance(action, dict):
            parameters = action.get("parameters", parameters or {})
            confidence = action.get("confidence", confidence)
            risk = action.get("risk", risk)
            act_name = action.get("action", "")
        elif hasattr(action, "action"):
            act_name = getattr(action, "action")
            parameters = getattr(action, "parameters", parameters or {})
            confidence = getattr(action, "confidence", confidence)
            risk = getattr(action, "risk", risk)
        else:
            act_name = str(action)

        params = parameters or {}
        act_upper = str(act_name).upper()
        sev_upper = incident_severity.upper()


        # ── 1. Hard Rule: Forbidden Destructive Actions (POLICY_REJECT) ───────
        # Note: Even if confidence == 1.0, high-confidence recommendations are rejected
        param_str = str(params).upper()
        if act_upper in FORBIDDEN_ACTIONS or any(f in param_str for f in ["DROP DATABASE", "RM -RF /", "PURGE_STORAGE"]):
            return PolicyEvaluationResult(
                decision=GovernanceDecision.POLICY_REJECT,
                risk="CRITICAL",
                policy_rule="RULE_FORBIDDEN_DESTRUCTIVE_ACTION",
                reason=f"Forbidden action '{act_upper}' is strictly prohibited by studio safety policy; cannot be executed by automation or approval.",
                is_blocked=True,
                audit_metadata={"rejected_by": "policy_engine", "action": act_upper, "confidence": confidence},
            )


        # ── 2. Mandatory Human Approval Rules ─────────────────────────────────

        # Rule 2A: MODIFY_PRODUCTION_SCENE -> HUMAN_APPROVAL
        if act_upper in ("MODIFY_PRODUCTION_SCENE", "MODIFY_SCENE", "EDIT_SCENE_FILE"):
            return PolicyEvaluationResult(
                decision=GovernanceDecision.HUMAN_APPROVAL,
                risk="HIGH",
                policy_rule="RULE_SCENE_MODIFICATION_REQUIRES_HUMAN_APPROVAL",
                reason="Modifying production scene files or stage geometry requires mandatory artist or TD approval.",
                is_blocked=False,
                audit_metadata={"action": act_upper, "confidence": confidence},
            )

        # Rule 2B: DELETE_ASSET -> HUMAN_APPROVAL
        if act_upper in ("DELETE_ASSET", "DELETE_CACHE", "PURGE_ASSET"):
            return PolicyEvaluationResult(
                decision=GovernanceDecision.HUMAN_APPROVAL,
                risk="HIGH",
                policy_rule="RULE_ASSET_DELETION_REQUIRES_HUMAN_APPROVAL",
                reason="Asset deletion is irreversible and requires explicit production supervisor approval.",
                is_blocked=False,
                audit_metadata={"action": act_upper, "confidence": confidence},
            )

        # Rule 2C: CRITICAL action -> HUMAN_APPROVAL
        effective_risk = (risk or "").upper()
        if effective_risk == "CRITICAL" or any(k in param_str for k in ["REBOOT", "KILL_PROCESS", "DROP"]):
            return PolicyEvaluationResult(
                decision=GovernanceDecision.HUMAN_APPROVAL,
                risk="CRITICAL",
                policy_rule="RULE_CRITICAL_RISK_REQUIRES_HUMAN_APPROVAL",
                reason="Actions with CRITICAL risk or host reboot parameters mandate human review.",
                is_blocked=False,
                audit_metadata={"action": act_upper, "risk": "CRITICAL"},
            )

        # Rule 2D: HIGH action -> HUMAN_APPROVAL
        target_pool = str(params.get("target_pool", "")).lower()
        is_expensive_pool = any(k in target_pool for k in ["80gb", "cloud", "burst", "a100", "h100"])
        if effective_risk == "HIGH" or is_expensive_pool:
            return PolicyEvaluationResult(
                decision=GovernanceDecision.HUMAN_APPROVAL,
                risk="HIGH",
                policy_rule="RULE_HIGH_RISK_REQUIRES_HUMAN_APPROVAL",
                reason="Actions with HIGH risk or premium resource allocations require human supervisor review.",
                is_blocked=False,
                audit_metadata={"action": act_upper, "risk": "HIGH", "target_pool": target_pool},
            )

        # ── 3. Operational Actions: RETRY_JOB ──────────────────────────────────
        if act_upper == "RETRY_JOB":
            # Example from specification:
            # RETRY_JOB + confidence >= 0.90 + risk = LOW -> AUTO_APPROVE
            if confidence >= 0.90 and (effective_risk == "LOW" or not effective_risk) and not is_expensive_pool:
                return PolicyEvaluationResult(
                    decision=GovernanceDecision.AUTO_APPROVE,
                    risk="LOW",
                    policy_rule="RULE_RETRY_HIGH_CONFIDENCE_LOW_RISK_AUTO_APPROVE",
                    reason="Standard farm job retry with confidence >= 0.90 and LOW risk is auto-approved.",
                    is_blocked=False,
                    audit_metadata={"action": act_upper, "confidence": confidence},
                )
            else:
                # Lower confidence or elevated risk -> requires human approval
                assigned_risk = "HIGH" if is_expensive_pool else "MEDIUM"
                return PolicyEvaluationResult(
                    decision=GovernanceDecision.HUMAN_APPROVAL,
                    risk=assigned_risk,
                    policy_rule="RULE_RETRY_CONDITIONAL_HUMAN_APPROVAL",
                    reason=f"Job retry requires human approval (Confidence: {confidence:.2f}, Risk: {assigned_risk}).",
                    is_blocked=False,
                    audit_metadata={"action": act_upper, "confidence": confidence, "risk": assigned_risk},
                )

        # ── 4. Read-Only / Informational Actions ──────────────────────────────
        if act_upper in ("NOTIFY_TEAM", "GENERATE_POSTMORTEM", "CREATE_INCIDENT", "NO_ACTION"):
            return PolicyEvaluationResult(
                decision=GovernanceDecision.AUTO_APPROVE,
                risk="LOW",
                policy_rule="RULE_INFORMATIONAL_ACTION_AUTO_APPROVE",
                reason=f"Informational action '{act_upper}' has LOW risk and is auto-approved.",
                is_blocked=False,
                audit_metadata={"action": act_upper},
            )

        # ── 5. Pipeline State Modifications ───────────────────────────────────
        if act_upper in ("ASSIGN_PIPELINE_TD", "UPDATE_SHOT_STATUS"):
            # If explicit confidence < 0.90 or incident critical, require human approval
            if sev_upper == "CRITICAL" or confidence < 0.90:
                return PolicyEvaluationResult(
                    decision=GovernanceDecision.HUMAN_APPROVAL,
                    risk="MEDIUM",
                    policy_rule="RULE_PIPELINE_OPERATION_HUMAN_APPROVAL",
                    reason=f"Action '{act_upper}' requires human confirmation (Confidence: {confidence:.2f}, Severity: {sev_upper}).",
                    is_blocked=False,
                    audit_metadata={"action": act_upper, "severity": sev_upper, "confidence": confidence},
                )
            return PolicyEvaluationResult(
                decision=GovernanceDecision.AUTO_APPROVE,
                risk="MEDIUM",
                policy_rule="RULE_STANDARD_PIPELINE_OPERATION_AUTO_APPROVE",
                reason=f"Standard pipeline operation '{act_upper}' is auto-approved under nominal conditions.",
                is_blocked=False,
                audit_metadata={"action": act_upper},
            )

        # ── 6. Worker & Daemon Operations ────────────────────────────────────
        if act_upper in ("RESTART_RENDER_DAEMON", "RESTART_WORKER", "RESTART_NODE_SERVICE"):
            decision = GovernanceDecision.AUTO_APPROVE if (confidence >= 0.90 and effective_risk == "LOW") else GovernanceDecision.HUMAN_APPROVAL
            return PolicyEvaluationResult(
                decision=decision,
                risk="MEDIUM",
                policy_rule="RULE_WORKER_DAEMON_RESTART",
                reason="Render daemon restart is classified as MEDIUM risk.",
                is_blocked=False,
                audit_metadata={"action": act_upper, "confidence": confidence},
            )

        if act_upper in ("OVERRIDE_FRAME_RANGE", "MODIFY_RENDER_SETTINGS"):
            return PolicyEvaluationResult(
                decision=GovernanceDecision.HUMAN_APPROVAL,
                risk="HIGH",
                policy_rule="RULE_FRAME_RANGE_OVERRIDE_HIGH_RISK",
                reason="Overriding frame ranges is classified as HIGH risk and mandates human review.",
                is_blocked=False,
                audit_metadata={"action": act_upper, "confidence": confidence},
            )

        # Default fallback: unknown action requires human review
        return PolicyEvaluationResult(
            decision=GovernanceDecision.HUMAN_APPROVAL,
            risk="HIGH",
            policy_rule="RULE_DEFAULT_CONSERVATIVE_HUMAN_APPROVAL",
            reason=f"Action '{act_upper}' is unclassified; conservative governance mandates human approval.",
            is_blocked=False,
            audit_metadata={"action": act_upper},
        )

