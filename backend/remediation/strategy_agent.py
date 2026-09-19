"""
Remediation Strategy Specialist Agent.
Proposes structured, sequenced remediation plans grounded in root cause diagnostic findings.
Applies deterministic risk policy rules for safety and human-in-the-loop governance.

STRICT INVARIANTS:
1. The remediation agent must NEVER execute the action. It only proposes actions.
2. LLM recommendations must NEVER bypass deterministic policy rules.
3. Every proposed action contains: action, reason, risk, confidence, requires_human_approval, parameters.
"""

from typing import Any, Optional, Union
import uuid

from backend.remediation.policy import DeterministicRiskPolicyEngine
from backend.remediation.schemas import (
    ActionType,
    RemediationActionProposal,
    RemediationInputContext,
    RemediationPlanProposal,
)


class RemediationStrategyAgent:
    """
    Remediation Strategy Specialist that maps root cause reasoning into
    structured, policy-evaluated remediation plan proposals.
    """

    def __init__(self, policy_engine: Optional[DeterministicRiskPolicyEngine] = None) -> None:
        self.policy_engine = policy_engine or DeterministicRiskPolicyEngine()

    def propose_plan(
        self,
        context: Union[RemediationInputContext, dict[str, Any]],
    ) -> RemediationPlanProposal:
        """
        Synthesize a structured remediation plan from root-cause analysis.
        STRICT RULE: Only proposes actions; NEVER executes them.
        """
        if isinstance(context, dict):
            ctx = RemediationInputContext.model_validate(context)
        else:
            ctx = context

        # Extract root cause info
        rca = ctx.root_cause_analysis
        if hasattr(rca, "root_cause"):
            root_cause = rca.root_cause
        elif isinstance(rca, dict):
            root_cause = rca.get("root_cause", "UNKNOWN_FAULT")
        else:
            root_cause = str(rca)

        inc_id = ctx.incident_id or f"inc-{uuid.uuid4().hex[:8]}"
        job_id = ctx.job_id or "job-current"
        shot_id = ctx.shot_id or "SH010"
        node_id = ctx.node_id or "node-blade-01"
        confidence = ctx.confidence
        severity = ctx.incident_severity.upper()

        proposed_raw_actions: list[dict[str, Any]] = []
        strategy_summary = ""
        rollback_plan = ""

        # ── 1. Strategy Mapping by Root Cause ─────────────────────────────────

        if root_cause in ("GPU_MEMORY_EXHAUSTION", "GPU_OUT_OF_MEMORY"):
            strategy_summary = f"Reroute job '{job_id}' from blade '{node_id}' to high-capacity 80GB GPU node pool."
            rollback_plan = f"If retry on 80GB GPU fails, revert shot '{shot_id}' status and assign to lead lighting TD."

            proposed_raw_actions = [
                {
                    "action": ActionType.NOTIFY_TEAM.value,
                    "reason": f"Notify lighting team of GPU OOM on job '{job_id}' (frame exceeded 24GB VRAM).",
                    "parameters": {"channel": "lighting-alerts", "severity": severity, "job_id": job_id},
                },
                {
                    "action": ActionType.UPDATE_SHOT_STATUS.value,
                    "reason": f"Mark shot '{shot_id}' as 'Farm Retrying' to prevent downstream compositing pickup.",
                    "parameters": {"shot_id": shot_id, "status": "FARM_RETRYING"},
                },
                {
                    "action": ActionType.RETRY_JOB.value,
                    "reason": f"Dispatch job '{job_id}' to 80GB GPU pool (supported by 14 historical precedents).",
                    "parameters": {
                        "job_id": job_id,
                        "target_pool": "gpu-80gb",
                        "retry_count": 1,
                        "previous_node": node_id,
                    },
                    "llm_suggested_risk": "LOW",  # Intentional test case for policy override
                    "llm_suggested_approval": False,
                },
                {
                    "action": ActionType.GENERATE_POSTMORTEM.value,
                    "reason": "Record VRAM memory allocation footprint in studio telemetry archive.",
                    "parameters": {"incident_id": inc_id, "job_id": job_id},
                },
            ]

        elif "ASSET" in root_cause or "CORRUPT" in root_cause:
            strategy_summary = f"Halt shot '{shot_id}' rendering; assign Pipeline TD to inspect and republish corrupted asset."
            rollback_plan = "Re-enable render queue once valid asset publish checksum is validated."

            proposed_raw_actions = [
                {
                    "action": ActionType.UPDATE_SHOT_STATUS.value,
                    "reason": f"Hold shot '{shot_id}' until asset geometry cache is republished.",
                    "parameters": {"shot_id": shot_id, "status": "BLOCKED_ON_ASSET"},
                },
                {
                    "action": ActionType.ASSIGN_PIPELINE_TD.value,
                    "reason": "Assign Pipeline TD to inspect corrupt asset cache and coordinate re-export.",
                    "parameters": {"incident_id": inc_id, "shot_id": shot_id, "role": "Pipeline_TD_Asset"},
                },
                {
                    "action": ActionType.NOTIFY_TEAM.value,
                    "reason": "Alert asset and lookdev departments of corrupt asset cache.",
                    "parameters": {"channel": "assets-alerts", "severity": severity},
                },
            ]

        elif "THERMAL" in root_cause or "HARDWARE" in root_cause:
            strategy_summary = f"Quarantine overheating blade '{node_id}' and reschedule job on healthy compute blade."
            rollback_plan = "Restore blade to cluster scheduler only after physical inspection and thermal pass."

            proposed_raw_actions = [
                {
                    "action": ActionType.NOTIFY_TEAM.value,
                    "reason": f"Alert IT infrastructure team of thermal trip (94C) on node '{node_id}'.",
                    "parameters": {"channel": "infra-ops", "node_id": node_id, "severity": "CRITICAL"},
                },
                {
                    "action": ActionType.UPDATE_SHOT_STATUS.value,
                    "reason": f"Update shot '{shot_id}' status to 'Rerouting'.",
                    "parameters": {"shot_id": shot_id, "status": "REROUTING"},
                },
                {
                    "action": ActionType.RETRY_JOB.value,
                    "reason": f"Retry job '{job_id}' on standard healthy blade pool excluding '{node_id}'.",
                    "parameters": {
                        "job_id": job_id,
                        "target_pool": "standard-healthy",
                        "exclude_nodes": [node_id],
                    },
                },
                {
                    "action": ActionType.ASSIGN_PIPELINE_TD.value,
                    "reason": f"Assign hardware engineer to inspect node '{node_id}'.",
                    "parameters": {"node_id": node_id, "role": "Hardware_Engineer"},
                },
            ]

        elif root_cause == "INSUFFICIENT_EVIDENCE":
            strategy_summary = f"No automatic remediation action taken for incident '{inc_id}' due to insufficient diagnostic evidence."
            rollback_plan = "None required (no automated mutation performed)."

            proposed_raw_actions = [
                {
                    "action": ActionType.NO_ACTION.value,
                    "reason": "Diagnostic evidence is insufficient to safely determine root cause; automated action prohibited.",
                    "parameters": {"incident_id": inc_id, "confidence": confidence},
                },
                {
                    "action": ActionType.CREATE_INCIDENT.value,
                    "reason": "Create triage ticket for manual root-cause investigation.",
                    "parameters": {"incident_id": inc_id, "severity": "LOW"},
                },
                {
                    "action": ActionType.ASSIGN_PIPELINE_TD.value,
                    "reason": "Assign on-call TD for manual diagnostics.",
                    "parameters": {"incident_id": inc_id},
                },
                {
                    "action": ActionType.NOTIFY_TEAM.value,
                    "reason": "Alert on-call TD that automated remediation was withheld pending manual diagnosis.",
                    "parameters": {"channel": "prod-coordinators", "incident_id": inc_id},
                },
            ]

        else:
            # Default fallback proposal
            strategy_summary = f"Default incident triage plan for root cause '{root_cause}'."
            rollback_plan = "Cancel investigation if shot finishes rendering."

            proposed_raw_actions = [
                {
                    "action": ActionType.NOTIFY_TEAM.value,
                    "reason": f"Alert team of anomalous failure: {root_cause}",
                    "parameters": {"channel": "pipeline-alerts"},
                },
                {
                    "action": ActionType.ASSIGN_PIPELINE_TD.value,
                    "reason": "Assign TD for root-cause confirmation.",
                    "parameters": {"incident_id": inc_id},
                },
            ]

        # ── 2. Apply Deterministic Risk Policy to Every Action ────────────────
        evaluated_actions: list[RemediationActionProposal] = []
        all_policy_logs: list[str] = []

        for raw_act in proposed_raw_actions:
            proposal, logs = self.policy_engine.evaluate_action(
                action=raw_act["action"],
                parameters=raw_act.get("parameters", {}),
                confidence=confidence,
                incident_severity=severity,
                reason=raw_act.get("reason", ""),
                llm_suggested_risk=raw_act.get("llm_suggested_risk"),
                llm_suggested_approval=raw_act.get("llm_suggested_approval"),
            )
            evaluated_actions.append(proposal)
            all_policy_logs.extend(logs)

        # ── 3. Compute Overall Plan Risk and Approval Gate ────────────────────
        overall_risk, overall_needs_approval = self.policy_engine.calculate_overall_plan_risk(evaluated_actions)

        return RemediationPlanProposal(
            incident_id=inc_id,
            root_cause=root_cause,
            strategy_summary=strategy_summary,
            overall_risk=overall_risk,
            requires_human_approval=overall_needs_approval,
            actions=evaluated_actions,
            rollback_plan=rollback_plan,
            policy_evaluation_log=all_policy_logs,
        )
