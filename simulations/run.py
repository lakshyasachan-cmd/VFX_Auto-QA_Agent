"""
CLI runner for VFX Failure Scenarios and End-to-End Simulation Pipeline.
Usage:
    python simulations/run.py --scenario gpu_oom
    python simulations/run.py --scenario render_node_failure --seed 42
    python simulations/run.py --all --seed 123
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Ensure root directory is on sys.path when executed directly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from simulations.runner import SimulationPipelineRunner
from simulations.scenarios import SCENARIO_MAP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("vfx.simulations.cli")


async def run_scenario_cli(scenario: str, seed: Optional[int], target: Optional[str], verbose: bool):
    runner = SimulationPipelineRunner()
    print("\n========================================================")
    print(f"[SIMULATION] TRIGGERING VFX SCENARIO: {scenario.upper()} (seed={seed})")
    print("========================================================")

    result = await runner.run(
        scenario_name=scenario,
        seed=seed,
        target_api_url=target,
    )

    print("\n[OK] PIPELINE EXECUTION COMPLETED SUCCESSFULLY!")
    print("--------------------------------------------------------")
    print(f"* Incident ID:       {result['incident_id']}")
    print(f"* Event Type:        {result['normalized_event']['event_type']}")
    print(f"* Severity:          {result['normalized_event']['severity']}")
    print(f"* Root Cause:        {result['reasoning']['root_cause']}")
    print(f"* Confidence:        {int(result['reasoning']['confidence'] * 100)}%")
    print(f"* Remediation Plan:  {result['remediation_plan']['strategy_summary']}")
    print(f"* Actions Evaluated: {len(result['approvals'])} action proposals")
    print(f"* MCP Dispatches:    {len(result['mcp_executions'])} tool executions")
    print("--------------------------------------------------------")

    if verbose:
        print("\n[AUDIT] DETAILED PIPELINE AUDIT TIMELINE:")
        for t in result["timeline"]:
            print(f"  [{t['timestamp']}] {t['stage']}: {json.dumps(t['details'])}")
        print("\n[RESULT] FULL RESULT JSON:")
        print(json.dumps(result, indent=2))


async def main():
    parser = argparse.ArgumentParser(description="VFX Pipeline Incident Simulation Runner")
    parser.add_argument(
        "--scenario",
        type=str,
        default="gpu_oom",
        help=f"Scenario to simulate. Options: {', '.join(sorted(set(SCENARIO_MAP.keys())))}",
    )
    parser.add_argument("--seed", type=int, default=None, help="Deterministic random seed for reproducibility")
    parser.add_argument("--target", type=str, default=None, help="Optional HTTP endpoint for event ingestion (e.g. http://localhost:8001/api/v1/events)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose JSON payloads and timeline")
    parser.add_argument("--all", action="store_true", help="Run all 8 realistic failure scenarios sequentially")

    args = parser.parse_args()

    if args.all:
        unique_scenarios = [
            "gpu_out_of_memory",
            "render_node_failure",
            "corrupted_frame",
            "missing_asset",
            "usd_dependency_failure",
            "vdb_file_failure",
            "texture_version_mismatch",
            "repeated_node_failure",
        ]
        for sc in unique_scenarios:
            await run_scenario_cli(sc, args.seed, args.target, args.verbose)
    else:
        await run_scenario_cli(args.scenario, args.seed, args.target, args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
