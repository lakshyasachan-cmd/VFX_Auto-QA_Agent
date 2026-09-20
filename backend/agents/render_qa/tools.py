"""
Render QA diagnostic tools for inspecting jobs, analyzing failed frames,
comparing metadata consistency, and detecting pixel/header corruption.
Never invents evidence; strictly extracts observed facts from data stores.
"""

from typing import Any, Optional
from backend.agents.render_qa.schemas import (
    FrameComparisonResult,
    FrameCorruptionReport,
    FrameInspectionDetail,
)
from backend.agents.render_qa.simulated_store import SimulatedRenderFarmStore, farm_store


def _get_store(store: Optional[Any]) -> Any:
    """Helper to lazily resolve active farm store or farm adapter."""
    if store is not None:
        return store
    try:
        from backend.integrations.render_farm.adapter import farm_adapter
        return farm_adapter
    except ImportError:
        return farm_store


def inspect_render_job(
    job_id: str,
    store: Optional[Any] = None,
) -> dict[str, Any]:
    """
    Tool 1: Inspects the overall render job record, renderer version, status, and frame counts.
    """
    s = _get_store(store)
    record = s.get_job_record(job_id)
    if not record:
        return {
            "found": False,
            "job_id": job_id,
            "error": f"Job '{job_id}' was not found in render farm database",
        }

    frames = record.get("frames", {})
    failed_frames = [f for f, data in frames.items() if data.get("status") == "FAILED" or data.get("exit_code", 0) != 0]
    completed_frames = [f for f, data in frames.items() if data.get("status") == "COMPLETED" and data.get("exit_code", 0) == 0]

    # Parse expected frame range if present
    expected_frames: set[int] = set()
    frame_range_str = record.get("frame_range", "")
    if "-" in frame_range_str:
        try:
            start, end = map(int, frame_range_str.split("-"))
            expected_frames = set(range(start, end + 1))
        except ValueError:
            pass

    recorded_frames = set(frames.keys())
    missing_frames = sorted(list(expected_frames - recorded_frames)) if expected_frames else []

    return {
        "found": True,
        "job_id": job_id,
        "project": record.get("project"),
        "sequence": record.get("sequence"),
        "shot": record.get("shot"),
        "renderer": record.get("renderer"),
        "renderer_version": record.get("renderer_version"),
        "status": record.get("status"),
        "node_id": record.get("node_id"),
        "frame_range": frame_range_str,
        "total_expected_frames": len(expected_frames) if expected_frames else len(recorded_frames),
        "completed_count": len(completed_frames),
        "failed_count": len(failed_frames),
        "missing_count": len(missing_frames),
        "failed_frames": sorted(failed_frames),
        "missing_frames": missing_frames,
    }


def inspect_failed_frames(
    job_id: str,
    frame_range: Optional[str] = None,
    store: Optional[Any] = None,
) -> list[FrameInspectionDetail]:
    """
    Tool 2: Inspects specific failed frames, extracting exact error logs, exit codes, and VRAM telemetry.
    """
    s = _get_store(store)
    record = s.get_job_record(job_id)
    if not record:
        return []

    frames = record.get("frames", {})
    target_frames: set[int] = set()

    if frame_range and "-" in frame_range:
        try:
            start, end = map(int, frame_range.split("-"))
            target_frames = set(range(start, end + 1))
        except ValueError:
            target_frames = set(frames.keys())
    else:
        target_frames = set(frames.keys())

    details: list[FrameInspectionDetail] = []
    for f in sorted(target_frames):
        fdata = frames.get(f)
        if not fdata:
            # Missing frame
            details.append(
                FrameInspectionDetail(
                    frame=f,
                    status="MISSING",
                    error_snippet="No task record or log found for frame",
                )
            )
            continue

        is_failed = fdata.get("status") == "FAILED" or fdata.get("exit_code", 0) != 0
        if is_failed:
            details.append(
                FrameInspectionDetail(
                    frame=f,
                    status="FAILED",
                    exit_code=fdata.get("exit_code"),
                    render_time_seconds=fdata.get("render_time"),
                    file_size_bytes=fdata.get("file_size"),
                    vram_peak_mb=fdata.get("vram_peak_mb"),
                    error_snippet=fdata.get("error_log"),
                    node_id=record.get("node_id"),
                )
            )

    return details


def compare_frame_metadata(
    job_id: str,
    frame_a: int,
    frame_b: int,
    store: Optional[Any] = None,
) -> FrameComparisonResult:
    """
    Tool 3: Compares metadata and metrics between two frames in a sequence to detect anomalies or drops.
    """
    s = _get_store(store)
    record = s.get_job_record(job_id)
    discrepancies: list[str] = []

    if not record:
        return FrameComparisonResult(
            frame_a=frame_a,
            frame_b=frame_b,
            resolution_match=False,
            channel_match=False,
            size_ratio=0.0,
            time_ratio=0.0,
            is_consistent=False,
            discrepancies=[f"Job '{job_id}' not found"],
        )

    frames = record.get("frames", {})
    fa = frames.get(frame_a)
    fb = frames.get(frame_b)

    if not fa or not fb:
        missing = [f for f, d in [(frame_a, fa), (frame_b, fb)] if d is None]
        return FrameComparisonResult(
            frame_a=frame_a,
            frame_b=frame_b,
            resolution_match=False,
            channel_match=False,
            size_ratio=0.0,
            time_ratio=0.0,
            is_consistent=False,
            discrepancies=[f"Frame(s) {missing} missing from farm task list"],
        )

    # Resolution check
    res_a = fa.get("resolution", "unknown")
    res_b = fb.get("resolution", "unknown")
    res_match = (res_a == res_b) and (res_a != "unknown")
    if res_a != res_b:
        discrepancies.append(f"Resolution mismatch: frame {frame_a} is {res_a}, while frame {frame_b} is {res_b}")

    # Channels check
    chan_a = fa.get("channels", [])
    chan_b = fb.get("channels", [])
    chan_match = (chan_a == chan_b) and bool(chan_a)
    if chan_a != chan_b:
        discrepancies.append(f"Channel layer mismatch: {chan_a} vs {chan_b}")

    # File size ratio
    size_a = max(1, fa.get("file_size", 1))
    size_b = max(1, fb.get("file_size", 1))
    size_ratio = round(size_b / size_a, 3)
    if size_ratio < 0.1 or size_ratio > 10.0:
        discrepancies.append(
            f"Severe file size anomaly: frame {frame_b} ({size_b} bytes) is {size_ratio}x of frame {frame_a} ({size_a} bytes)"
        )

    # Render time ratio
    time_a = max(0.1, fa.get("render_time", 1.0))
    time_b = max(0.1, fb.get("render_time", 1.0))
    time_ratio = round(time_b / time_a, 3)
    if time_ratio < 0.1 or time_ratio > 10.0:
        discrepancies.append(
            f"Abnormal render duration: frame {frame_b} took {time_b}s vs frame {frame_a} ({time_a}s)"
        )

    is_consistent = len(discrepancies) == 0

    return FrameComparisonResult(
        frame_a=frame_a,
        frame_b=frame_b,
        resolution_match=res_match,
        channel_match=chan_match,
        size_ratio=size_ratio,
        time_ratio=time_ratio,
        is_consistent=is_consistent,
        discrepancies=discrepancies,
    )


def detect_frame_corruption(
    job_id: str,
    frame: int,
    store: Optional[Any] = None,
) -> FrameCorruptionReport:
    """
    Tool 4: Analyzes physical output file on disk for NaN pixels, truncated headers, or 0-byte corruptions.
    """
    s = _get_store(store)
    telemetry = s.get_output_file_telemetry(job_id, frame)

    if telemetry is None:
        return FrameCorruptionReport(
            frame=frame,
            is_corrupted=True,
            corruption_type="MISSING_FILE",
            nan_pixel_percentage=0.0,
            file_size_bytes=0,
            header_valid=False,
            details=f"Output frame file for frame {frame} does not exist on storage",
        )

    file_size = telemetry.get("size", 0)
    nan_pixels = telemetry.get("nan_pixels", 0.0)
    header_valid = telemetry.get("header_valid", True)

    # 1. Check 0-byte file
    if file_size == 0:
        return FrameCorruptionReport(
            frame=frame,
            is_corrupted=True,
            corruption_type="ZERO_BYTE",
            file_size_bytes=0,
            header_valid=False,
            details=f"Frame {frame} is an empty 0-byte file",
        )

    # 2. Check Truncated header
    if not header_valid or file_size < 1024:
        return FrameCorruptionReport(
            frame=frame,
            is_corrupted=True,
            corruption_type="TRUNCATED_HEADER",
            file_size_bytes=file_size,
            header_valid=False,
            details=f"Frame {frame} header is corrupt or truncated ({file_size} bytes)",
        )

    # 3. Check NaN/Inf pixels
    if nan_pixels > 0.0:
        return FrameCorruptionReport(
            frame=frame,
            is_corrupted=True,
            corruption_type="NAN_PIXELS",
            nan_pixel_percentage=nan_pixels,
            file_size_bytes=file_size,
            header_valid=True,
            details=f"Frame {frame} beauty channel contains {nan_pixels}% NaN/Inf pixel values",
        )

    return FrameCorruptionReport(
        frame=frame,
        is_corrupted=False,
        corruption_type=None,
        nan_pixel_percentage=0.0,
        file_size_bytes=file_size,
        header_valid=True,
        details="Frame pixels and header are valid and intact",
    )
