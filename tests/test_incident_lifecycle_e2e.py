# end-to-end incident lifecycle test suite
import copy
import pytest
from unittest.mock import MagicMock, patch

from backend.agents.supervisor.schemas import (
    AgentFindingDTO,
    EvidenceItemDTO,
    InvestigationRequest,
)
from backend.agents.supervisor.supervisor_agent import SupervisorAgent
from backend.events.schemas import CanonicalEvent
from backend.events.service import EventIngestionService
from backend.governance.policy_engine import GovernanceDecision, PolicyEngine
from backend.governance.schemas import ApprovalStatus
from backend.governance.service import GovernanceService
from backend.mcp.gateway import MCPExecutionGateway
from backend.mcp.schemas import MCPExecutionContext, RetryRenderJobParams
from backend.mcp.server import MCPServer
from backend.reasoning.engine import RootCauseReasoningEngine
from backend.reasoning.schemas import ReasoningContextInput, RootCauseAnalysis
from backend.remediation.schemas import ActionType, RiskLevel
from backend.remediation.strategy_agent import RemediationStrategyAgent
from simulations.runner import SimulationPipelineRunner
from simulations.scenarios import get_scenario_event
from tests.test_supervisor_agent import (
    MockHistoricalEvidenceAgent,
    MockHardwareDiagnosticAgent,
    MockRenderQAAgent,
)


@pytest.mark.asyncio
async def test_scenario_1_gpu_oom_complete_lifecycle():
    runner = SimulationPipelineRunner()
    result = await runner.run('gpu_out_of_memory', seed=42, auto_approve_human_gate=True)

    assert result['success'] is True
    assert result['incident_id'].startswith('inc-')
    assert result['status'] == 'RESOLVED'
    assert 'successfully remediated' in result['resolution_summary']

    assert result['normalized_event']['event_type'] == 'RENDER_JOB_FAILED'
    investigation = result['investigation']
    specialists_used = [f['agent_name'] for f in investigation['findings']]
    assert any('Hardware' in name for name in specialists_used)
    assert any(e['evidence_type'] in ('HISTORICAL_PRECEDENT', 'HISTORICAL_RECORD') for e in investigation['evidence'])

    reasoning = result['reasoning']
    assert reasoning['root_cause'] in ('GPU_MEMORY_EXHAUSTION', 'GPU_OUT_OF_MEMORY')
    assert reasoning['confidence'] >= 0.85

    remediation = result['remediation_plan']
    actions = [a['action'] for a in remediation['actions']]
    assert ActionType.RETRY_JOB.value in actions

    approvals = result['approvals']
    assert len(approvals) >= 1
    for a in approvals:
        assert a['status'] in (ApprovalStatus.AUTO_APPROVED.value, ApprovalStatus.APPROVED.value)

    mcp_calls = result['mcp_executions']
    assert len(mcp_calls) >= 1
    assert any(call['tool_name'] == 'retry_render_job' for call in mcp_calls)
    assert all(call['success'] is True for call in mcp_calls)
    assert len(result['audit_records']) >= len(mcp_calls)


@pytest.mark.asyncio
async def test_scenario_2_missing_asset_human_approval_gate():
    governance = GovernanceService(policy_engine=PolicyEngine())
    mcp = MCPServer(governance_svc=governance)
    runner = SimulationPipelineRunner(governance_svc=governance, mcp_server_instance=mcp)

    result_gated = await runner.run('missing_asset', seed=101, auto_approve_human_gate=False)

    assert result_gated['success'] is True
    investigation = result_gated['investigation']
    specialists = [f['agent_name'] for f in investigation['findings']]
    assert any('Asset' in name for name in specialists)

    pending_approvals = [a for a in result_gated['approvals'] if a['status'] == ApprovalStatus.PENDING.value]
    assert len(pending_approvals) >= 1, 'Missing asset remediation must require human approval'

    for p in pending_approvals:
        assert p['id'] not in [e.get('approval_id') for e in result_gated['mcp_executions']]

    # Find the pending approval for UPDATE_SHOT_STATUS
    shot_status_approval = next(a for a in pending_approvals if a['action'] == 'UPDATE_SHOT_STATUS')
    approved_dto = governance.approve_action(
        approval_id=shot_status_approval['id'],
        actor='lead_pipeline_td',
        notes='Asset path verified in staging repository; confirmed safe to execute.',
    )
    assert approved_dto.status == ApprovalStatus.APPROVED.value

    context = MCPExecutionContext(
        approval_id=approved_dto.id,
        actor='lead_pipeline_td',
        incident_id=result_gated['incident_id'],
        plan_id=result_gated['remediation_plan']['plan_id'],
    )
    mcp_resp = mcp.call_tool(
        tool_name='update_shot_status',
        parameters={
            'project': 'DUNE_PART_3',
            'sequence': 'SQ010',
            'shot': 'SH0010',
            'new_status': 'on_hold',
            'notes': 'Hold shot pending asset republish',
            'updated_by': 'lead_pipeline_td',
        },
        context=context,
    )
    assert mcp_resp.success is True
    assert mcp_resp.tool_name == 'update_shot_status'

    audit_records = mcp.gateway.audit_records
    assert any(rec['approval_id'] == approved_dto.id for rec in audit_records)


@pytest.mark.asyncio
async def test_scenario_3_corrupted_frame_lifecycle():
    runner = SimulationPipelineRunner()
    result = await runner.run('corrupted_frame', seed=202)

    assert result['success'] is True
    assert result['normalized_event']['event_type'] == 'FRAME_CORRUPTION_DETECTED'

    findings = result['investigation']['findings']
    qa_findings = [f for f in findings if 'RenderQA' in f['agent_name'] or 'QA' in f['finding_type']]
    assert len(qa_findings) >= 1

    reasoning = result['reasoning']
    assert 'CORRUPT' in reasoning['root_cause'].upper() or 'FRAME' in reasoning['root_cause'].upper()
    assert reasoning['confidence'] >= 0.70

    remediation = result['remediation_plan']
    assert len(remediation['actions']) >= 1
    assert any(a['action'] in (ActionType.UPDATE_SHOT_STATUS.value, ActionType.ASSIGN_PIPELINE_TD.value, ActionType.NOTIFY_TEAM.value) for a in remediation['actions'])


@pytest.mark.asyncio
async def test_scenario_4_insufficient_evidence_no_automatic_action():
    sparse_event = {
        'source': 'unknown_monitor',
        'event_type': 'RENDER_JOB_FAILED',
        'project': 'DUNE_PART_3',
        'shot': 'SH0010',
        'message': 'Generic unclassified process termination',
        'timestamp': '2026-09-08T12:00:00Z',
    }

    reasoning_engine = RootCauseReasoningEngine()
    reasoning_input = ReasoningContextInput(
        incident=sparse_event,
        render_qa_findings=[],
        hardware_findings=[],
        asset_findings=[],
        historical_evidence={},
    )
    analysis = reasoning_engine.analyze(reasoning_input)

    assert analysis.root_cause == 'INSUFFICIENT_EVIDENCE'
    assert analysis.confidence <= 0.20
    assert analysis.recommended_action == 'DISPATCH_INVESTIGATION_MANUAL'

    strategy_agent = RemediationStrategyAgent()
    remediation_plan = strategy_agent.propose_plan({
        'root_cause_analysis': analysis.model_dump(),
        'confidence': analysis.confidence,
        'incident_severity': analysis.severity,
        'incident_id': 'inc-sparse-001',
    })

    action_types = [a.action for a in remediation_plan.actions]
    assert ActionType.NO_ACTION.value in action_types
    assert ActionType.RETRY_JOB.value not in action_types
    assert ActionType.UPDATE_SHOT_STATUS.value not in action_types


@pytest.mark.asyncio
async def test_scenario_5_conflicting_agent_findings_human_review():
    qa_agent = MockRenderQAAgent(
        custom_findings=[
            AgentFindingDTO(
                agent_name='RenderQAAgent',
                finding_type='SHADER_BUG',
                category='software',
                severity='HIGH',
                confidence=0.92,
                title='Scene shader failed with memory corruption bug in Arnold plugin',
            )
        ]
    )
    hw_agent = MockHardwareDiagnosticAgent(
        custom_findings=[
            AgentFindingDTO(
                agent_name='HardwareDiagnosticAgent',
                finding_type='GPU_HARDWARE_FAULT',
                category='hardware',
                severity='CRITICAL',
                confidence=0.90,
                title='Compute blade GPU thermal threshold exceeded (94C junction temp)',
            )
        ]
    )

    supervisor = SupervisorAgent(
        sub_agents=[qa_agent, hw_agent, MockHistoricalEvidenceAgent()]
    )

    req = InvestigationRequest(
        incident_id='inc-conflict-lifecycle',
        event={
            'source': 'deadline',
            'event_type': 'RENDER_JOB_FAILED',
            'project': 'AVATAR_3',
            'job_id': 'job-conflict-99',
            'node_id': 'render-node-12',
            'error_code': 'CRASH',
        },
    )
    result = await supervisor.investigate_incident(req)

    assert len(result.conflicts) >= 1
    conflict = result.conflicts[0]
    assert 'RenderQAAgent' in conflict.conflicting_agents
    assert 'HardwareDiagnosticAgent' in conflict.conflicting_agents
    assert 'Contradictory Root Cause' in conflict.reason
    assert result.confidence < 0.90


@pytest.mark.asyncio
async def test_scenario_6_mcp_failure_incident_remains_unresolved():
    governance = GovernanceService(policy_engine=PolicyEngine())
    mcp = MCPServer(governance_svc=governance)

    failing_retry_handler = MagicMock(side_effect=RuntimeError('Farm submission service unreachable: Connection timeout'))
    # Use isolated tool registry dict copy so global TOOL_REGISTRY is not mutated
    isolated_registry = dict(mcp.gateway.tool_registry)
    isolated_registry['retry_render_job'] = (RetryRenderJobParams, failing_retry_handler)
    mcp.gateway.tool_registry = isolated_registry

    runner = SimulationPipelineRunner(governance_svc=governance, mcp_server_instance=mcp)
    result = await runner.run('gpu_out_of_memory', seed=777, auto_approve_human_gate=True)

    assert result['success'] is True
    assert result['status'] == 'UNRESOLVED'
    assert 'Remediation action failed' in result['resolution_summary']

    failed_mcp_calls = [c for c in result['mcp_executions'] if not c['success']]
    assert len(failed_mcp_calls) >= 1
    assert 'Farm submission service unreachable' in failed_mcp_calls[0]['error']

    mcp_audits = [r for r in mcp.gateway.audit_records if r.get('status') == 'FAILED']
    assert len(mcp_audits) >= 1
    assert 'Farm submission service unreachable' in str(mcp_audits[0].get('error'))


@pytest.mark.asyncio
async def test_scenario_7_duplicate_event_idempotency():
    ingestion_service = EventIngestionService()
    event_payload = get_scenario_event('render_node_failure', seed=888)

    resp_1 = await ingestion_service.ingest_event(event_payload)
    assert resp_1.status == 'accepted'
    assert resp_1.duplicate is False
    assert resp_1.normalized_event is not None

    resp_2 = await ingestion_service.ingest_event(event_payload)
    assert resp_2.status == 'duplicate_ignored'
    assert resp_2.duplicate is True
    assert resp_2.normalized_event is None
    assert 'Duplicate event ignored' in resp_2.message


@pytest.mark.asyncio
async def test_scenario_8_unauthorized_action_policy_blocked():
    policy_engine = PolicyEngine()
    governance = GovernanceService(policy_engine=policy_engine)
    mcp = MCPServer(governance_svc=governance)

    forbidden_action = 'DROP_DATABASE'
    eval_result = policy_engine.evaluate_policy(action=forbidden_action)
    assert eval_result.is_blocked is True
    assert eval_result.decision == GovernanceDecision.POLICY_REJECT
    assert eval_result.risk == 'CRITICAL'

    appr_dto = governance.create_approval_request(action=forbidden_action)
    assert appr_dto.status == ApprovalStatus.REJECTED.value

    with pytest.raises(ValueError, match='terminal status'):
        governance.approve_action(appr_dto.id, actor='lead_td')

    context_unauthorized = MCPExecutionContext(
        approval_id='approved-fake-id',
        actor='untrusted',
        incident_id='inc-sec-01',
        plan_id='plan-sec-01',
    )
    resp = mcp.call_tool(
        tool_name='retry_render_job',
        parameters={'job_id': 'job-sec-01'},
        context=context_unauthorized,
    )
    assert resp.success is False
    assert 'Unauthorized actor' in resp.error


@pytest.mark.asyncio
async def test_complete_lineage_traceability():
    runner = SimulationPipelineRunner()
    result = await runner.run('vdb_file_failure', seed=999, auto_approve_human_gate=True)

    assert result['normalized_event'] is not None
    assert 'event_id' in result['normalized_event']
    assert 'correlation_id' in result['normalized_event']

    assert result['investigation'] is not None
    assert len(result['investigation']['findings']) > 0

    assert len(result['investigation']['evidence']) > 0

    assert result['reasoning'] is not None
    assert result['reasoning']['root_cause'] != ''
    assert result['reasoning']['confidence'] > 0

    assert result['remediation_plan'] is not None
    assert len(result['remediation_plan']['actions']) > 0

    assert len(result['approvals']) > 0
    for appr in result['approvals']:
        assert appr['policy_evaluated'] is not None
        assert appr['status'] in ('AUTO_APPROVED', 'APPROVED')

    assert len(result['mcp_executions']) > 0
    for mcp_call in result['mcp_executions']:
        assert mcp_call['success'] is True

    assert len(result['audit_records']) > 0
    audit = result['audit_records'][-1]
    assert 'timestamp' in audit
    assert 'actor' in audit
    assert 'tool_name' in audit
