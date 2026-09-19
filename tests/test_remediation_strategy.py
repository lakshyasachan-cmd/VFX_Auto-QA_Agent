"""
Unit and integration tests for the Remediation Strategy Specialist subsystem.
Tests verify:
1. Scenario 1: GPU OOM Remediation Plan (proposes RETRY_JOB on 80GB GPU with HIGH risk)
2. Scenario 2: Corrupted Asset Remediation Plan (proposes ASSIGN_PIPELINE_TD and UPDATE_SHOT_STATUS)
3. Scenario 3: Thermal Throttling Remediation Plan (proposes node quarantine and rerouting)
4. Scenario 4: Insufficient Evidence Remediation Plan (proposes ticket creation and manual TD assignment)
5. Scenario 5: Deterministic Policy Overrules LLM Approval Bypass Attempt
6. Scenario 6: All Action Types Conform to Required JSON Schema
7. Scenario 7: Destructive Parameter Detection Escalates Risk to CRITICAL
8. Scenario 8: Low Confidence (<0.75) Escalates Actions to Mandatory Human Approval
9. Scenario 9: Overall Plan Risk Matches Highest Constituent Action Risk
10. Scenario 10: Strict Non-Execution Invariance (Agent only proposes, never executes)
"""

import pytest

from backend.remediation.policy import DeterministicRiskPolicyEngine
from backend.remediation.schemas import (
    ActionType,
    RemediationActionProposal,
    RemediationInputContext,
    RemediationPlanProposal,
    RiskLevel,
)
from backend.remediation.strategy_agent import RemediationStrategyAgent


@pytest.fixture
def strategy_agent():
    return RemediationStrategyAgent()


# ── Scenario 1: GPU OOM Remediation Plan ───────────────────────────────────────

def test_scenario_1_gpu_oom_remediation_plan(strategy_agent):
    """
    Validates GPU OOM remediation plan:
    Proposes NOTIFY_TEAM, UPDATE_SHOT_STATUS, RETRY_JOB on 80GB GPU pool, and GENERATE_POSTMORTEM.
    """
    context = RemediationInputContext(
        root_cause_analysis={
            "root_cause": "GPU_MEMORY_EXHAUSTION",
            "recommended_action": "RETRY_ON_HEALTHY_NODE",
        },
        evidence=["99.6% VRAM utilization", "CUDA exit code 137"],
        confidence=0.97,
        incident_severity="HIGH",
        incident_id="inc-oom-101",
        job_id="job-1042",
        shot_id="SH020",
        node_id="node-blade-42",
    )

    plan = strategy_agent.propose_plan(context)

    assert plan.incident_id == "inc-oom-101"
    assert plan.root_cause == "GPU_MEMORY_EXHAUSTION"
    assert plan.overall_risk == RiskLevel.HIGH.value
    assert plan.requires_human_approval is True

    # Check constituent actions
    action_types = [a.action for a in plan.actions]
    assert ActionType.NOTIFY_TEAM.value in action_types
    assert ActionType.UPDATE_SHOT_STATUS.value in action_types
    assert ActionType.RETRY_JOB.value in action_types
    assert ActionType.GENERATE_POSTMORTEM.value in action_types

    # Validate RETRY_JOB action specifically
    retry_action = next(a for a in plan.actions if a.action == ActionType.RETRY_JOB.value)
    assert retry_action.risk == RiskLevel.HIGH.value
    assert retry_action.requires_human_approval is True
    assert retry_action.parameters["target_pool"] == "gpu-80gb"
    assert retry_action.confidence == pytest.approx(0.97, abs=0.01)


# ── Scenario 2: Corrupted Asset Remediation Plan ──────────────────────────────

def test_scenario_2_corrupted_asset_remediation_plan(strategy_agent):
    """Validates corrupted asset plan: updates shot status, assigns TD, notifies team."""
    context = RemediationInputContext(
        root_cause_analysis={
            "root_cause": "CORRUPTED_ASSET_CACHE",
            "recommended_action": "REPUBLISH_AND_SYNC_ASSET",
        },
        evidence=["Truncated Ogawa header (16 bytes)"],
        confidence=0.96,
        incident_severity="CRITICAL",
        incident_id="inc-asset-202",
        shot_id="SH030",
    )

    plan = strategy_agent.propose_plan(context)

    assert plan.root_cause == "CORRUPTED_ASSET_CACHE"
    assert plan.requires_human_approval is True  # CRITICAL severity requires approval

    action_types = [a.action for a in plan.actions]
    assert ActionType.UPDATE_SHOT_STATUS.value in action_types
    assert ActionType.ASSIGN_PIPELINE_TD.value in action_types
    assert ActionType.NOTIFY_TEAM.value in action_types

    shot_action = next(a for a in plan.actions if a.action == ActionType.UPDATE_SHOT_STATUS.value)
    assert shot_action.parameters["status"] == "BLOCKED_ON_ASSET"


# ── Scenario 3: Thermal Throttling Remediation Plan ───────────────────────────

def test_scenario_3_thermal_throttling_remediation_plan(strategy_agent):
    """Validates hardware thermal throttling remediation plan."""
    context = RemediationInputContext(
        root_cause_analysis={
            "root_cause": "HARDWARE_THERMAL_THROTTLING",
            "recommended_action": "QUARANTINE_NODE_AND_COOL",
        },
        evidence=["GPU temp 94C", "PCIe degraded to x1"],
        confidence=0.95,
        incident_severity="CRITICAL",
        node_id="node-blade-12",
    )

    plan = strategy_agent.propose_plan(context)
    action_types = [a.action for a in plan.actions]

    assert ActionType.NOTIFY_TEAM.value in action_types
    assert ActionType.RETRY_JOB.value in action_types
    assert ActionType.ASSIGN_PIPELINE_TD.value in action_types

    retry_act = next(a for a in plan.actions if a.action == ActionType.RETRY_JOB.value)
    assert "node-blade-12" in retry_act.parameters.get("exclude_nodes", [])


# ── Scenario 4: Insufficient Evidence Remediation Plan ────────────────────────

def test_scenario_4_insufficient_evidence_remediation_plan(strategy_agent):
    """Validates fallback plan for insufficient diagnostic evidence."""
    context = RemediationInputContext(
        root_cause_analysis={
            "root_cause": "INSUFFICIENT_EVIDENCE",
            "recommended_action": "DISPATCH_INVESTIGATION_MANUAL",
        },
        evidence=[],
        confidence=0.20,
        incident_severity="LOW",
        incident_id="inc-inconclusive-303",
    )

    plan = strategy_agent.propose_plan(context)

    action_types = [a.action for a in plan.actions]
    assert ActionType.CREATE_INCIDENT.value in action_types
    assert ActionType.ASSIGN_PIPELINE_TD.value in action_types
    assert ActionType.NOTIFY_TEAM.value in action_types


# ── Scenario 5: Deterministic Policy Overrules LLM Approval Bypass ────────────

def test_scenario_5_deterministic_policy_overrules_llm_bypass():
    """
    CRITICAL INVARIANT: LLM recommendations must NEVER bypass deterministic policy rules.
    If an LLM suggests risk='LOW' and requires_human_approval=False for a high-resource RETRY_JOB,
    the policy engine MUST override both and enforce HIGH risk + mandatory human approval.
    """
    policy = DeterministicRiskPolicyEngine()

    proposal, logs = policy.evaluate_action(
        action="RETRY_JOB",
        parameters={"job_id": "job-999", "target_pool": "gpu-80gb"},
        confidence=0.95,
        incident_severity="HIGH",
        reason="LLM test attempt to bypass governance",
        llm_suggested_risk="LOW",              # Attempted bypass
        llm_suggested_approval=False,          # Attempted bypass
    )

    # 1. Assert bypass was stopped
    assert proposal.risk == RiskLevel.HIGH.value
    assert proposal.requires_human_approval is True

    # 2. Assert policy evaluation logged the override
    assert any("Policy OVERRIDE" in log for log in logs)
    assert any("strictly enforced deterministic risk 'HIGH'" in log for log in logs)
    assert any("strictly enforced human review" in log for log in logs)


# ── Scenario 6: All Action Types Schema Compliance ────────────────────────────

def test_scenario_6_all_action_types_schema_compliance():
    """Verifies that every action type outputs the exact schema required by specification."""
    policy = DeterministicRiskPolicyEngine()

    action_samples = [
        ("RETRY_JOB", {"job_id": "j1"}),
        ("ASSIGN_PIPELINE_TD", {"role": "Lead_TD"}),
        ("UPDATE_SHOT_STATUS", {"status": "HOLD"}),
        ("CREATE_INCIDENT", {"ticket": "T-100"}),
        ("NOTIFY_TEAM", {"channel": "alerts"}),
        ("GENERATE_POSTMORTEM", {"id": "inc-1"}),
        ("NO_ACTION", {}),
    ]

    for action_name, params in action_samples:
        proposal, _ = policy.evaluate_action(
            action=action_name,
            parameters=params,
            confidence=0.90,
            incident_severity="MEDIUM",
            reason=f"Testing schema for {action_name}",
        )
        dump = proposal.model_dump()

        # Strict specification check
        assert "action" in dump and dump["action"] == action_name
        assert "reason" in dump and len(dump["reason"]) > 0
        assert "risk" in dump and dump["risk"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert "confidence" in dump and isinstance(dump["confidence"], float)
        assert "requires_human_approval" in dump and isinstance(dump["requires_human_approval"], bool)
        assert "parameters" in dump and isinstance(dump["parameters"], dict)


# ── Scenario 7: Destructive Parameter Risk Escalation ─────────────────────────

def test_scenario_7_destructive_parameter_escalation():
    """Detects reboot/delete keywords in parameters and escalates risk to CRITICAL."""
    policy = DeterministicRiskPolicyEngine()

    proposal, logs = policy.evaluate_action(
        action="ASSIGN_PIPELINE_TD",
        parameters={"action_detail": "Execute node reboot and delete caches"},
        confidence=0.90,
        incident_severity="MEDIUM",
    )

    assert proposal.risk == RiskLevel.CRITICAL.value
    assert proposal.requires_human_approval is True
    assert any("ESCALATION" in log and "CRITICAL" in log for log in logs)


# ── Scenario 8: Low Confidence Escalation ─────────────────────────────────────

def test_scenario_8_low_confidence_escalation():
    """Actions escalate to mandatory human approval when confidence is below 0.75."""
    policy = DeterministicRiskPolicyEngine()

    proposal, logs = policy.evaluate_action(
        action="UPDATE_SHOT_STATUS",
        parameters={"status": "INVESTIGATING"},
        confidence=0.60,  # Below 0.75 threshold
        incident_severity="LOW",
    )

    assert proposal.risk == RiskLevel.HIGH.value
    assert proposal.requires_human_approval is True
    assert any("Confidence 0.60 < 0.75" in log for log in logs)


# ── Scenario 9: Overall Plan Risk Calculation ─────────────────────────────────

def test_scenario_9_overall_plan_risk_matches_highest_action():
    """Overall plan risk reflects the highest constituent risk level."""
    policy = DeterministicRiskPolicyEngine()

    actions = [
        RemediationActionProposal(
            action="NOTIFY_TEAM",
            reason="Inform team",
            risk="LOW",
            confidence=0.95,
            requires_human_approval=False,
        ),
        RemediationActionProposal(
            action="UPDATE_SHOT_STATUS",
            reason="Hold shot",
            risk="MEDIUM",
            confidence=0.95,
            requires_human_approval=False,
        ),
        RemediationActionProposal(
            action="RETRY_JOB",
            reason="Farm retry",
            risk="HIGH",
            confidence=0.95,
            requires_human_approval=True,
        ),
    ]

    overall_risk, needs_approval = policy.calculate_overall_plan_risk(actions)
    assert overall_risk == "HIGH"
    assert needs_approval is True


# ── Scenario 10: Strict Non-Execution Invariance ──────────────────────────────

def test_scenario_10_agent_does_not_execute_actions(strategy_agent):
    """
    STRICT INVARIANT: The remediation agent must NEVER execute the action.
    It only proposes actions.
    """
    context = RemediationInputContext(
        root_cause_analysis={"root_cause": "GPU_MEMORY_EXHAUSTION", "recommended_action": "RETRY"},
        confidence=0.97,
        incident_severity="HIGH",
    )

    plan = strategy_agent.propose_plan(context)
    plan_dict = plan.model_dump()

    # Verify no execution or mutation attributes exist in output
    assert "execute" not in plan_dict
    assert "execution_status" not in plan_dict
    assert "mcp_client" not in plan_dict
    assert "watsonx_call" not in plan_dict
    assert "ran_at" not in plan_dict
