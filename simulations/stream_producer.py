"""
Live Studio Incident Stream Producer.
Simulates a real 24/7 visual effects render farm and production pipeline.
Continuously or burst-emits realistic studio failure events into the backend API.

Usage:
    # Run continuous stream every 45 seconds:
    python simulations/stream_producer.py --interval 45

    # Instantly seed 3 fresh incidents for a live demo, then stream every 60s:
    python simulations/stream_producer.py --burst 3 --interval 60

    # Target a remote deployed server:
    python simulations/stream_producer.py --url https://your-domain.com/api/v1/events
"""

import argparse
import asyncio
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env", override=True)

import httpx
from simulations.scenarios import SCENARIO_MAP, get_scenario_event
from simulations.runner import SimulationPipelineRunner


DEFAULT_SCENARIOS = [
    "gpu_out_of_memory",
    "corrupted_frame",
    "missing_asset",
    "render_node_failure",
    "usd_dependency_failure",
    "vdb_file_failure",
    "texture_version_mismatch",
    "repeated_node_failure",
]


async def emit_event_http(api_url: str, event_payload: dict, api_key: str) -> bool:
    """Send an incident event payload directly over HTTP to the ingestion API."""
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(api_url, json=event_payload, headers=headers)
            if resp.status_code in (200, 202):
                data = resp.json()
                print(f"  [HTTP 202 ACCEPTED] Event ID: {data.get('event_id')} | Source: {event_payload.get('source')}")
                return True
            else:
                print(f"  [HTTP {resp.status_code} ERROR] {resp.text}")
                return False
    except Exception as exc:
        print(f"  [CONNECTION FAILED] Could not reach {api_url}: {exc}")
        return False


async def run_pipeline_direct(scenario_name: str, runner: SimulationPipelineRunner) -> dict:
    """Run event through the full multi-agent pipeline (Supervisor + Gemini + DB save)."""
    print(f"\n⚡ [AGENT DISPATCH] Investigating '{scenario_name}' via ADK Supervisor & Gemini...")
    result = await runner.run(scenario_name=scenario_name)
    inc_id = result.get("incident_id")
    root_cause = result.get("reasoning", {}).get("root_cause", "UNKNOWN")
    confidence = int(result.get("reasoning", {}).get("confidence", 0) * 100)
    print(f"  ✓ Incident Created: {inc_id}")
    print(f"  ✓ Gemini Root Cause: {root_cause} ({confidence}% confidence)")
    print(f"  ✓ Status in PostgreSQL: {result.get('status')}")
    return result


async def main():
    parser = argparse.ArgumentParser(description="Live Studio Incident Streamer for VFX Mission Control")
    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("EVENT_API_URL", "http://localhost:8001/api/v1/events"),
        help="Backend event ingestion API URL",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=45,
        help="Seconds between live incidents (default: 45s)",
    )
    parser.add_argument(
        "--burst",
        type=int,
        default=2,
        help="Number of initial incidents to generate immediately on startup (default: 2)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        default=True,
        help="Run full multi-agent pipeline directly to populate PostgreSQL and Gemini analysis",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("VFX_SYSTEM_API_KEY", "c5774bc066a6b4076f696d88df1a5160b511481bd5056a39303a582d703de5c7"),
        help="API Key for authenticated HTTP ingestion",
    )

    args = parser.parse_args()

    print("=" * 65)
    print("🎬 VFX MISSION CONTROL — LIVE STUDIO INCIDENT STREAMER")
    print("=" * 65)
    print(f"Target API:    {args.url}")
    print(f"Stream Interval: Every {args.interval} seconds")
    print(f"Initial Burst:   {args.burst} incidents")
    print(f"Pipeline Mode:   Full Multi-Agent + Gemini AI Reasoning")
    print("=" * 65)

    runner = SimulationPipelineRunner() if args.direct else None

    # Step 1: Initial Burst
    if args.burst > 0:
        print(f"\n🚀 [BURST MODE] Instantly seeding {args.burst} studio incidents for live dashboard...")
        scenarios_to_burst = random.sample(DEFAULT_SCENARIOS, min(args.burst, len(DEFAULT_SCENARIOS)))
        for i, sc in enumerate(scenarios_to_burst, 1):
            print(f"\n[{i}/{args.burst}] Simulating: {sc.upper()}")
            if args.direct and runner:
                await run_pipeline_direct(sc, runner)
            else:
                event = get_scenario_event(sc)
                await emit_event_http(args.url, event, args.api_key)
            await asyncio.sleep(2)
        print("\n✅ Burst complete! Initial incidents are now visible on the frontend.\n")

    # Step 2: Continuous Streaming Loop
    iteration = 1
    while True:
        sc = random.choice(DEFAULT_SCENARIOS)
        next_interval = args.interval + random.randint(-5, 10)
        next_interval = max(10, next_interval)

        print(f"\n📡 [STREAM #{iteration}] Next studio failure incoming in {next_interval}s...")
        await asyncio.sleep(next_interval)

        print(f"\n💥 [STUDIO FAILURE OCCURRED] Scenario: {sc.upper()}")
        if args.direct and runner:
            await run_pipeline_direct(sc, runner)
        else:
            event = get_scenario_event(sc)
            await emit_event_http(args.url, event, args.api_key)

        iteration += 1


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ Stream producer stopped by user.")
