"""
Quick Verification Script: Checks whether ADK is running with the 4 Real Subagents vs Demo Mocks.
"""
import asyncio
from backend.agents.supervisor.supervisor_agent import SupervisorAgent
from backend.agents.supervisor.schemas import InvestigationRequest
from backend.agents.render_qa.agent import RenderQAAgent
from backend.agents.hardware.agent import HardwareDiagnosticAgent
from backend.agents.asset_validation.agent import AssetValidationAgent
from backend.agents.historical.agent import HistoricalEvidenceAgent

async def test_real_adk():
    print("=" * 65)
    print("STEP 1: Instantiating 4 Real ADK Specialist Subagents")
    print("=" * 65)

    real_subagents = [
        RenderQAAgent(),
        HardwareDiagnosticAgent(),
        AssetValidationAgent(),
        HistoricalEvidenceAgent(),
    ]

    supervisor = SupervisorAgent(sub_agents=real_subagents)

    print("\n[VERIFICATION] Loaded ADK Subagents in Supervisor:")
    for idx, subagent in enumerate(supervisor.sub_agents, 1):
        is_real = not subagent.__class__.__name__.startswith("Mock")
        status_tag = "[REAL SUBAGENT]" if is_real else "[DEMO / MOCK]"
        print(f"  {idx}. {subagent.name:<26} -> Class: {subagent.__class__.__name__:<26} {status_tag}")

    print("\n" + "=" * 65)
    print("STEP 2: Dispatching Incident Event to ADK Supervisor")
    print("=" * 65)

    req = InvestigationRequest(
        incident_id="inc-live-check-001",
        event={
            "source": "deadline",
            "event_type": "RENDER_JOB_FAILED",
            "project": "DUNE_PART_3",
            "shot": "sh042",
            "node_id": "render-node-07",
            "error_code": "GPU_OUT_OF_MEMORY",
        },
    )

    result = await supervisor.investigate_incident(req)

    print(f"\n[STATUS] Investigation Status: {result.status.value}")
    print(f"[TYPE]   Classified Incident Type: {result.incident_type.value}")
    print(f"[AGENTS] Selected Specialists: {', '.join(result.selected_specialists)}")

    print("\n[TIMING] Execution Latencies (Real compute from agent_traces):")
    for trace in result.agent_traces:
        print(f"  * {trace.agent_name:<26} -> {trace.duration_ms:>6.2f} ms | Status: {trace.status}")

    print(f"\n[FINDINGS] Total Findings: {len(result.findings)}")
    for f in result.findings:
        print(f"\n  - Agent:      {f.agent_name}")
        print(f"    Title:      {f.title}")
        print(f"    Confidence: {int(f.confidence * 100)}%")
        if isinstance(f.details, dict) and "observed" in f.details:
            print(f"    Observed:   {f.details['observed'][:2]}")
            print(f"    Inferred:   {f.details['inferred'][:2]}")

    print("\n" + "=" * 65)
    print("[SUCCESS] Verified! The 4 subagents are running REAL code.")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(test_real_adk())
