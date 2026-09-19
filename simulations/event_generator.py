"""
VFX Production Incident & Event Generator.
Simulates realistic events from Deadline, Tractor, OpenCue, ShotGrid, and Asset Storage.
Can be executed via CLI to fire webhooks or imported programmatically for testing.
"""

import argparse
import json
import random
import time
from datetime import datetime, timezone
from typing import Any, Optional
import httpx


PROJECTS = ["Project_A", "Avatar_Sequel", "Dune_Part_3", "Cyberpunk_Cinematic"]
SEQUENCES = ["SQ010", "SQ020", "SQ030", "SQ045"]
SHOTS = ["SH010", "SH020", "SH045", "SH100"]
RENDER_NODES = [f"render-node-{i:02d}" for i in range(1, 65)]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_render_oom_event(
    project: Optional[str] = None,
    sequence: Optional[str] = None,
    shot: Optional[str] = None,
    job_id: Optional[str] = None,
    node_id: Optional[str] = None,
) -> dict[str, Any]:
    """Generates a realistic Deadline GPU Out-Of-Memory render failure."""
    proj = project or random.choice(PROJECTS)
    seq = sequence or random.choice(SEQUENCES)
    sh = shot or random.choice(SHOTS)
    jid = job_id or f"job_{random.randint(1000, 9999)}"
    nid = node_id or random.choice(RENDER_NODES)
    frame = random.randint(1001, 1150)

    return {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": proj,
        "sequence": seq,
        "shot": sh,
        "job_id": jid,
        "node_id": nid,
        "frame": frame,
        "error_code": "GPU_OUT_OF_MEMORY",
        "exit_code": 137,
        "message": f"Arnold CUDA error: Out of memory on {nid} while allocating 4096MB VRAM buffer on frame {frame}",
        "timestamp": now_iso(),
        "metrics": {
            "vram_used_mb": 24576,
            "vram_total_mb": 24576,
            "ram_used_gb": 64.0,
            "gpu_temperature_c": 82.5,
        },
        "metadata": {
            "renderer": "arnold-7.2.4",
            "dcc": "maya-2025",
            "plugin_version": "mtoa-5.3.1",
        },
    }


def create_render_started_event(
    project: Optional[str] = None,
    sequence: Optional[str] = None,
    shot: Optional[str] = None,
    job_id: Optional[str] = None,
    node_id: Optional[str] = None,
) -> dict[str, Any]:
    """Generates a render job started event."""
    return {
        "source": "deadline",
        "event_type": "RENDER_JOB_STARTED",
        "project": project or random.choice(PROJECTS),
        "sequence": sequence or random.choice(SEQUENCES),
        "shot": shot or random.choice(SHOTS),
        "job_id": job_id or f"job_{random.randint(1000, 9999)}",
        "node_id": node_id or random.choice(RENDER_NODES),
        "message": "Render task dispatched to worker blade",
        "timestamp": now_iso(),
        "metadata": {"priority": 50, "pool": "gpu-lighting"},
    }


def create_render_completed_event(
    project: Optional[str] = None,
    sequence: Optional[str] = None,
    shot: Optional[str] = None,
    job_id: Optional[str] = None,
    node_id: Optional[str] = None,
) -> dict[str, Any]:
    """Generates a render job completed event."""
    return {
        "source": "deadline",
        "event_type": "RENDER_JOB_COMPLETED",
        "project": project or random.choice(PROJECTS),
        "sequence": sequence or random.choice(SEQUENCES),
        "shot": shot or random.choice(SHOTS),
        "job_id": job_id or f"job_{random.randint(1000, 9999)}",
        "node_id": node_id or random.choice(RENDER_NODES),
        "message": "All frames rendered successfully without warnings",
        "timestamp": now_iso(),
        "metrics": {"render_time_seconds": 342.18, "peak_vram_mb": 14200},
    }


def create_node_unhealthy_event(node_id: Optional[str] = None) -> dict[str, Any]:
    """Generates a compute blade hardware failure (thermal throttling / PCIe bus error)."""
    nid = node_id or random.choice(RENDER_NODES)
    return {
        "source": "tractor",
        "event_type": "NODE_UNHEALTHY",
        "node_id": nid,
        "error_code": "PCIE_BUS_DEGRADED",
        "message": f"Hardware alert on {nid}: PCIe bus link degraded from x16 to x1, GPU thermal threshold exceeded (94C)",
        "timestamp": now_iso(),
        "severity": "CRITICAL",
        "metrics": {
            "gpu_temperature_c": 94.0,
            "pcie_link_width": 1,
            "pcie_link_expected": 16,
            "ecc_errors_uncorrectable": 14,
        },
        "metadata": {
            "blade_rack": "RACK-B-04",
            "gpu_model": "NVIDIA RTX 6000 Ada",
        },
    }


def create_asset_validation_event(
    project: Optional[str] = None,
    shot: Optional[str] = None,
    asset_path: Optional[str] = None,
) -> dict[str, Any]:
    """Generates a missing or corrupt USD/texture asset validation failure."""
    proj = project or random.choice(PROJECTS)
    sh = shot or random.choice(SHOTS)
    path = asset_path or f"/prod/{proj}/shots/{sh}/assets/char/hero/tex/diffuse.1001.exr"

    return {
        "source": "asset_storage",
        "event_type": "ASSET_VALIDATION_FAILED",
        "project": proj,
        "shot": sh,
        "asset_name": path,
        "error_code": "USD_SUBCOMPONENT_MISSING",
        "message": f"Asset validation failed: required texture reference '{path}' does not exist on storage cluster",
        "timestamp": now_iso(),
        "metadata": {
            "stage_path": f"/prod/{proj}/shots/{sh}/usd/lighting.usd",
            "missing_file": path,
            "storage_mount": "/mnt/vfx_prod_storage",
        },
    }


def create_frame_corruption_event(
    project: Optional[str] = None,
    shot: Optional[str] = None,
    job_id: Optional[str] = None,
    frame: Optional[int] = None,
) -> dict[str, Any]:
    """Generates a frame corruption detection event (0-byte file, NaN pixel values)."""
    proj = project or random.choice(PROJECTS)
    sh = shot or random.choice(SHOTS)
    jid = job_id or f"job_{random.randint(1000, 9999)}"
    f_num = frame or random.randint(1001, 1080)

    return {
        "source": "opencue",
        "event_type": "FRAME_CORRUPTION_DETECTED",
        "project": proj,
        "shot": sh,
        "job_id": jid,
        "frame": f_num,
        "error_code": "EXR_NAN_PIXELS_DETECTED",
        "message": f"Frame {f_num} for shot {sh} failed post-render QA check: 18.4% of beauty channel pixels contain NaN values",
        "timestamp": now_iso(),
        "metrics": {
            "nan_pixel_percentage": 18.4,
            "file_size_bytes": 4520194,
        },
        "metadata": {
            "frame_path": f"/prod/{proj}/renders/{sh}/beauty.{f_num:04d}.exr",
            "qc_checker": "OpenEXR-Validator-v2",
        },
    }


def generate_scenario(scenario_name: str) -> list[dict[str, Any]]:
    """Generate a realistic set of events matching a named studio scenario."""
    scenarios = {
        "oom": [create_render_oom_event()],
        "node_failure": [create_node_unhealthy_event()],
        "asset_missing": [create_asset_validation_event()],
        "bad_frame": [create_frame_corruption_event()],
        "render_lifecycle": [
            create_render_started_event(job_id="job_9999"),
            create_render_oom_event(job_id="job_9999"),
        ],
        "cascading_outage": [
            create_node_unhealthy_event(node_id="render-node-12"),
            create_render_oom_event(node_id="render-node-12", job_id="job_501"),
            create_render_oom_event(node_id="render-node-12", job_id="job_502"),
        ],
    }

    if scenario_name in scenarios:
        return scenarios[scenario_name]

    # Fallback to random selection across all types
    generators = [
        create_render_oom_event,
        create_node_unhealthy_event,
        create_asset_validation_event,
        create_frame_corruption_event,
    ]
    return [random.choice(generators)()]


def send_event_to_api(event: dict[str, Any], target_url: str) -> tuple[int, dict[str, Any]]:
    """Send single event to target HTTP API."""
    with httpx.Client(timeout=10.0) as client:
        response = client.post(target_url, json=event)
        try:
            return response.status_code, response.json()
        except Exception:
            return response.status_code, {"raw_text": response.text}


def main():
    parser = argparse.ArgumentParser(description="VFX Incident & Event Generator")
    parser.add_argument(
        "--scenario",
        choices=["oom", "node_failure", "asset_missing", "bad_frame", "render_lifecycle", "cascading_outage", "random"],
        default="oom",
        help="Incident scenario to simulate",
    )
    parser.add_argument("--count", type=int, default=1, help="Number of scenario iterations to generate")
    parser.add_argument("--target", type=str, default=None, help="Target API URL (e.g. http://localhost:8001/api/v1/events)")
    parser.add_argument("--interval", type=float, default=0.2, help="Interval in seconds between events")

    args = parser.parse_args()

    for i in range(args.count):
        events = generate_scenario(args.scenario)
        for event in events:
            if args.target:
                print(f"[{i+1}/{args.count}] Dispatching {event['event_type']} to {args.target}...")
                status_code, resp = send_event_to_api(event, args.target)
                print(f" -> Response [{status_code}]: {json.dumps(resp, indent=2)}")
            else:
                print(json.dumps(event, indent=2))

            if args.interval > 0:
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
