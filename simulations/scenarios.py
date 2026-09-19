"""
Realistic VFX Production Failure Scenarios.
Implements the 8 required failure scenarios with rich production context
and deterministic seed support for full reproducibility.
"""

from datetime import datetime, timezone
import random
from typing import Any, Optional


PROJECTS = ["DUNE_PART_3", "AVATAR_3", "BLADE_RUNNER_2099", "SOLARIS_VFX"]
SEQUENCES = ["SQ010", "SQ020", "SQ040", "SQ085"]
SHOTS = ["SH0010", "SH0050", "SH0120", "SH0340"]
RENDER_NODES = [f"node-blade-{i:02d}" for i in range(1, 49)]


def now_iso(seed: Optional[int] = None) -> str:
    """Return deterministic ISO timestamp when seed is supplied, or current UTC timestamp."""
    if seed is not None:
        # Deterministic base timestamp for reproducible tests
        base_sec = 1718000000 + (seed % 100000)
        return datetime.fromtimestamp(base_sec, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_rng(seed: Optional[int] = None) -> random.Random:
    """Return a seeded Random instance or global random."""
    return random.Random(seed) if seed is not None else random.Random()


# ─────────────────────────────────────────────────────────────
# 1. GPU_OUT_OF_MEMORY
# ─────────────────────────────────────────────────────────────
def scenario_gpu_out_of_memory(seed: Optional[int] = None) -> dict[str, Any]:
    """
    Arnold CUDA Out of Memory failure during volume texture loading.
    """
    rng = get_rng(seed)
    proj = rng.choice(PROJECTS)
    seq = rng.choice(SEQUENCES)
    sh = rng.choice(SHOTS)
    node = rng.choice(RENDER_NODES)
    job_id = f"job-arnold-{rng.randint(1000, 9999)}"
    frame = rng.randint(1001, 1050)

    return {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": proj,
        "sequence": seq,
        "shot": sh,
        "job_id": job_id,
        "node_id": node,
        "frame": frame,
        "error_code": "GPU_OUT_OF_MEMORY",
        "exit_code": 137,
        "message": f"Arnold CUDA error 2: Out of memory on {node} while allocating 4096MB VRAM buffer on frame {frame}",
        "timestamp": now_iso(seed),
        "metrics": {
            "vram_used_mb": 48920,
            "vram_total_mb": 49152,
            "gpu_temperature_c": 84.5,
            "failed_frame": frame,
        },
        "metadata": {
            "renderer": "arnold-7.3.1",
            "dcc": "maya-2025",
            "volume_cache": f"/prod/{proj}/{seq}/{sh}/fx/fire_density.vdb",
            "recommended_pool": "gpu-80gb",
        },
    }


# ─────────────────────────────────────────────────────────────
# 2. RENDER_NODE_FAILURE
# ─────────────────────────────────────────────────────────────
def scenario_render_node_failure(seed: Optional[int] = None) -> dict[str, Any]:
    """
    Compute blade hardware failure (PCIe bus link degradation / thermal throttle).
    """
    rng = get_rng(seed)
    node = rng.choice(RENDER_NODES)

    return {
        "source": "tractor",
        "event_type": "NODE_UNHEALTHY",
        "node_id": node,
        "error_code": "PCIE_BUS_DEGRADED",
        "message": f"Hardware alert on {node}: PCIe link width degraded to x1, GPU thermal threshold exceeded (94.2C)",
        "timestamp": now_iso(seed),
        "severity": "CRITICAL",
        "metrics": {
            "gpu_temperature_c": 94.2,
            "pcie_link_width": 1,
            "pcie_link_expected": 16,
            "ecc_errors_uncorrectable": 14,
        },
        "metadata": {
            "blade_rack": "RACK-B-04",
            "gpu_model": "NVIDIA RTX 6000 Ada",
            "quarantine_recommended": True,
        },
    }


# ─────────────────────────────────────────────────────────────
# 3. CORRUPTED_FRAME
# ─────────────────────────────────────────────────────────────
def scenario_corrupted_frame(seed: Optional[int] = None) -> dict[str, Any]:
    """
    Post-render QA automated check detects NaN pixel values in beauty pass.
    """
    rng = get_rng(seed)
    proj = rng.choice(PROJECTS)
    seq = rng.choice(SEQUENCES)
    sh = rng.choice(SHOTS)
    job_id = f"job-qc-{rng.randint(1000, 9999)}"
    frame = rng.randint(1010, 1080)

    return {
        "source": "opencue",
        "event_type": "FRAME_CORRUPTION_DETECTED",
        "project": proj,
        "sequence": seq,
        "shot": sh,
        "job_id": job_id,
        "frame": frame,
        "error_code": "EXR_NAN_PIXELS_DETECTED",
        "message": f"Frame {frame} for shot {sh} failed post-render QC check: 24.8% of beauty channel pixels contain NaN values",
        "timestamp": now_iso(seed),
        "metrics": {
            "nan_pixel_percentage": 24.8,
            "file_size_bytes": 1824102,
        },
        "metadata": {
            "frame_path": f"/prod/{proj}/renders/{sh}/beauty.{frame:04d}.exr",
            "qc_checker": "OpenEXR-Validator-v2",
        },
    }


# ─────────────────────────────────────────────────────────────
# 4. MISSING_ASSET
# ─────────────────────────────────────────────────────────────
def scenario_missing_asset(seed: Optional[int] = None) -> dict[str, Any]:
    """
    Missing geometry asset file on shared studio SAN.
    """
    rng = get_rng(seed)
    proj = rng.choice(PROJECTS)
    seq = rng.choice(SEQUENCES)
    sh = rng.choice(SHOTS)
    asset_name = f"/prod/{proj}/{seq}/{sh}/assets/hero_creature_geo.usd"

    return {
        "source": "asset_storage",
        "event_type": "ASSET_VALIDATION_FAILED",
        "project": proj,
        "sequence": seq,
        "shot": sh,
        "asset_name": asset_name,
        "error_code": "ASSET_FILE_NOT_FOUND",
        "message": f"Asset validation failed: required geometry '{asset_name}' is missing on storage mount",
        "timestamp": now_iso(seed),
        "metadata": {
            "missing_file": asset_name,
            "storage_mount": "/mnt/vfx_san_01",
        },
    }


# ─────────────────────────────────────────────────────────────
# 5. USD_DEPENDENCY_FAILURE
# ─────────────────────────────────────────────────────────────
def scenario_usd_dependency_failure(seed: Optional[int] = None) -> dict[str, Any]:
    """
    USD Stage composition failure with broken sublayer dependency.
    """
    rng = get_rng(seed)
    proj = rng.choice(PROJECTS)
    seq = rng.choice(SEQUENCES)
    sh = rng.choice(SHOTS)
    layer = f"/prod/{proj}/{seq}/{sh}/usd/layers/environment_props_v003.usd"

    return {
        "source": "asset_storage",
        "event_type": "ASSET_VALIDATION_FAILED",
        "project": proj,
        "sequence": seq,
        "shot": sh,
        "asset_name": layer,
        "error_code": "USD_BROKEN_REFERENCE",
        "message": f"USD stage composition error: unable to resolve sublayer '{layer}' referenced by root lighting.usd",
        "timestamp": now_iso(seed),
        "metadata": {
            "stage_path": f"/prod/{proj}/{seq}/{sh}/usd/lighting.usd",
            "unresolved_sublayer": layer,
        },
    }


# ─────────────────────────────────────────────────────────────
# 6. VDB_FILE_FAILURE
# ─────────────────────────────────────────────────────────────
def scenario_vdb_file_failure(seed: Optional[int] = None) -> dict[str, Any]:
    """
    Corrupted OpenVDB volume header aborts render decompressor.
    """
    rng = get_rng(seed)
    proj = rng.choice(PROJECTS)
    seq = rng.choice(SEQUENCES)
    sh = rng.choice(SHOTS)
    vdb_path = f"/prod/{proj}/{seq}/{sh}/fx/explosion_smoke.1024.vdb"

    return {
        "source": "asset_storage",
        "event_type": "ASSET_VALIDATION_FAILED",
        "project": proj,
        "sequence": seq,
        "shot": sh,
        "asset_name": vdb_path,
        "error_code": "VDB_HEADER_CORRUPTED",
        "message": f"OpenVDB decompressor abort: magic bytes mismatch in '{vdb_path}' (file truncated)",
        "timestamp": now_iso(seed),
        "metadata": {
            "corrupt_file": vdb_path,
            "expected_magic": "0x56444220",
        },
    }


# ─────────────────────────────────────────────────────────────
# 7. TEXTURE_VERSION_MISMATCH
# ─────────────────────────────────────────────────────────────
def scenario_texture_version_mismatch(seed: Optional[int] = None) -> dict[str, Any]:
    """
    Published scene references deprecated texture version incompatible with color pipeline.
    """
    rng = get_rng(seed)
    proj = rng.choice(PROJECTS)
    seq = rng.choice(SEQUENCES)
    sh = rng.choice(SHOTS)
    tex_path = f"/prod/{proj}/{seq}/{sh}/textures/creature_skin_diffuse_v001.tx"

    return {
        "source": "asset_storage",
        "event_type": "ASSET_VALIDATION_FAILED",
        "project": proj,
        "sequence": seq,
        "shot": sh,
        "asset_name": tex_path,
        "error_code": "TEXTURE_VERSION_INCOMPATIBLE",
        "message": f"Texture validation failed: '{tex_path}' is deprecated version v001 (minimum required is v003 with ACEScg color space)",
        "timestamp": now_iso(seed),
        "metadata": {
            "current_version": "v001",
            "required_version": "v003",
            "color_space": "sRGB_Linear (expected ACEScg)",
        },
    }


# ─────────────────────────────────────────────────────────────
# 8. REPEATED_NODE_FAILURE
# ─────────────────────────────────────────────────────────────
def scenario_repeated_node_failure(seed: Optional[int] = None) -> dict[str, Any]:
    """
    Flapping render blade that failed 3 consecutive render jobs within 15 minutes.
    """
    rng = get_rng(seed)
    node = rng.choice(RENDER_NODES)

    return {
        "source": "tractor",
        "event_type": "NODE_UNHEALTHY",
        "node_id": node,
        "error_code": "REPEATED_NODE_FAILURE",
        "message": f"Flapping blade detected: {node} has failed 3 consecutive jobs in 15 minutes with SIGSEGV in nvidia-smi",
        "timestamp": now_iso(seed),
        "severity": "CRITICAL",
        "metrics": {
            "consecutive_failures": 3,
            "failure_window_minutes": 15,
            "gpu_driver_state": "XID_31_GPU_EXCEPTION",
        },
        "metadata": {
            "quarantine_action": "QUARANTINE_NODE_IMMEDIATE",
        },
    }


SCENARIO_MAP: dict[str, Any] = {
    "gpu_out_of_memory": scenario_gpu_out_of_memory,
    "gpu_oom": scenario_gpu_out_of_memory,
    "render_node_failure": scenario_render_node_failure,
    "node_failure": scenario_render_node_failure,
    "corrupted_frame": scenario_corrupted_frame,
    "bad_frame": scenario_corrupted_frame,
    "missing_asset": scenario_missing_asset,
    "usd_dependency_failure": scenario_usd_dependency_failure,
    "usd_failure": scenario_usd_dependency_failure,
    "vdb_file_failure": scenario_vdb_file_failure,
    "vdb_failure": scenario_vdb_file_failure,
    "texture_version_mismatch": scenario_texture_version_mismatch,
    "texture_mismatch": scenario_texture_version_mismatch,
    "repeated_node_failure": scenario_repeated_node_failure,
}


def get_scenario_event(name: str, seed: Optional[int] = None) -> dict[str, Any]:
    """Retrieve event payload for any named failure scenario with optional seed."""
    canonical_name = name.lower().strip().replace("-", "_")
    if canonical_name not in SCENARIO_MAP:
        raise ValueError(
            f"Unknown scenario '{name}'. Available scenarios: {', '.join(sorted(SCENARIO_MAP.keys()))}"
        )
    return SCENARIO_MAP[canonical_name](seed=seed)
