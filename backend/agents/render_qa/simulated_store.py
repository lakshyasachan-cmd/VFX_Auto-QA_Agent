"""
Simulated farm storage and metadata registry for Render QA investigations.
Provides realistic fixtures for render jobs, frame outputs, error logs, and corrupted pixels.
"""

from typing import Any, Optional


class SimulatedRenderFarmStore:
    """
    In-memory farm database providing simulated job logs, task states, and frame files.
    """

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._load_default_scenarios()

    def _load_default_scenarios(self) -> None:
        """Seed pre-configured failure scenarios for testing."""

        # ── Scenario 1: GPU Out-Of-Memory Failure (Arnold) ───────────────
        self._jobs["job_oom_arnold"] = {
            "job_id": "job_oom_arnold",
            "project": "Avatar3",
            "sequence": "SQ010",
            "shot": "SH001",
            "renderer": "arnold",
            "renderer_version": "7.2.4.0",
            "dcc": "maya-2025",
            "frame_range": "1001-1050",
            "status": "FAILED",
            "node_id": "render-node-42",
            "frames": {
                1001: {"status": "COMPLETED", "render_time": 420.5, "file_size": 48200100, "vram_peak_mb": 18200, "exit_code": 0},
                1041: {"status": "COMPLETED", "render_time": 440.1, "file_size": 49100200, "vram_peak_mb": 22100, "exit_code": 0},
                1042: {
                    "status": "FAILED",
                    "render_time": 120.4,
                    "file_size": 0,
                    "vram_peak_mb": 24576,
                    "exit_code": 137,
                    "error_log": (
                        "00:02:00 24576MB ERROR   | [gpu] CUDA error: Out of memory while allocating 4096MB buffer.\n"
                        "00:02:00 24576MB ERROR   | [gpu] Total VRAM available: 24576MB. Requested: 28672MB.\n"
                        "00:02:01 24576MB FATAL   | Render process terminated with exit code 137 (SIGKILL / OOM)."
                    ),
                },
            },
            "output_files": {
                1001: {"path": "/prod/renders/SH001/beauty.1001.exr", "size": 48200100, "nan_pixels": 0.0, "header_valid": True},
                1041: {"path": "/prod/renders/SH001/beauty.1041.exr", "size": 49100200, "nan_pixels": 0.0, "header_valid": True},
                1042: None,  # File was never written due to OOM
            },
        }

        # ── Scenario 2: Missing Frames in Sequence (V-Ray) ───────────────
        self._jobs["job_missing_frames"] = {
            "job_id": "job_missing_frames",
            "project": "Dune3",
            "sequence": "SQ020",
            "shot": "SH010",
            "renderer": "vray",
            "renderer_version": "6.20.00",
            "frame_range": "1001-1020",
            "status": "FAILED",
            "node_id": "render-node-15",
            "frames": {
                f: {"status": "COMPLETED", "render_time": 300.0, "file_size": 35000000, "exit_code": 0}
                for f in range(1001, 1021)
                if f not in [1012, 1013, 1014, 1015]
            },
            "output_files": {
                f: {"path": f"/prod/renders/SH010/beauty.{f}.exr", "size": 35000000, "nan_pixels": 0.0, "header_valid": True}
                for f in range(1001, 1021)
                if f not in [1012, 1013, 1014, 1015]
            },
            # Note: Frames 1012-1015 are omitted from frames and output_files (missing)
        }

        # ── Scenario 3: Corrupted Output Frame with NaN Pixels (RenderMan)
        self._jobs["job_corrupt_nan_pixels"] = {
            "job_id": "job_corrupt_nan_pixels",
            "project": "Cyberpunk",
            "sequence": "SQ040",
            "shot": "SH045",
            "renderer": "renderman",
            "renderer_version": "26.1",
            "frame_range": "1020-1030",
            "status": "COMPLETED",
            "node_id": "render-node-08",
            "frames": {
                1024: {"status": "COMPLETED", "render_time": 510.0, "file_size": 42000000, "exit_code": 0},
                1025: {"status": "COMPLETED", "render_time": 490.0, "file_size": 12, "exit_code": 0},  # Truncated 12-byte header
            },
            "output_files": {
                1024: {"path": "/prod/renders/SH045/beauty.1024.exr", "size": 42000000, "nan_pixels": 18.4, "header_valid": True},
                1025: {"path": "/prod/renders/SH045/beauty.1025.exr", "size": 12, "nan_pixels": 0.0, "header_valid": False},
            },
        }

        # ── Scenario 4: Frame Metadata & Size Inconsistency ──────────────
        self._jobs["job_frame_inconsistency"] = {
            "job_id": "job_frame_inconsistency",
            "project": "Avatar3",
            "sequence": "SQ010",
            "shot": "SH002",
            "renderer": "arnold",
            "renderer_version": "7.2.4.0",
            "frame_range": "1001-1005",
            "status": "COMPLETED",
            "node_id": "render-node-30",
            "frames": {
                1001: {"status": "COMPLETED", "render_time": 850.0, "file_size": 52000000, "resolution": "3840x2160", "channels": ["R", "G", "B", "A", "Z", "N"]},
                1002: {"status": "COMPLETED", "render_time": 14.0, "file_size": 110000, "resolution": "1920x1080", "channels": ["R", "G", "B"]},  # Severe mismatch!
            },
            "output_files": {
                1001: {"path": "/prod/renders/SH002/beauty.1001.exr", "size": 52000000, "nan_pixels": 0.0, "header_valid": True},
                1002: {"path": "/prod/renders/SH002/beauty.1002.exr", "size": 110000, "nan_pixels": 0.0, "header_valid": True},
            },
        }

        # ── Scenario 5: Repeated Failure Pattern Across Frames (Houdini Mantra)
        self._jobs["job_repeated_shader_segfault"] = {
            "job_id": "job_repeated_shader_segfault",
            "project": "SciFi_Series",
            "sequence": "SQ090",
            "shot": "SH080",
            "renderer": "mantra",
            "renderer_version": "20.0.590",
            "frame_range": "1001-1003",
            "status": "FAILED",
            "node_id": "render-node-18",
            "frames": {
                1001: {
                    "status": "FAILED",
                    "exit_code": 139,
                    "error_log": "Mantra: caught signal 11 (SIGSEGV) in shader 'libwood_procedural.so' at address 0x00000000.",
                },
                1002: {
                    "status": "FAILED",
                    "exit_code": 139,
                    "error_log": "Mantra: caught signal 11 (SIGSEGV) in shader 'libwood_procedural.so' at address 0x00000000.",
                },
                1003: {
                    "status": "FAILED",
                    "exit_code": 139,
                    "error_log": "Mantra: caught signal 11 (SIGSEGV) in shader 'libwood_procedural.so' at address 0x00000000.",
                },
            },
            "output_files": {
                1001: None,
                1002: None,
                1003: None,
            },
        }

    def register_job(self, job_id: str, data: dict[str, Any]) -> None:
        """Allow test suites to register ad-hoc or dynamic simulated job scenarios."""
        self._jobs[job_id] = data

    def get_job_record(self, job_id: str) -> Optional[dict[str, Any]]:
        return self._jobs.get(job_id)

    def get_frame_record(self, job_id: str, frame: int) -> Optional[dict[str, Any]]:
        job = self.get_job_record(job_id)
        if not job:
            return None
        return job.get("frames", {}).get(frame)

    def get_output_file_telemetry(self, job_id: str, frame: int) -> Optional[dict[str, Any]]:
        job = self.get_job_record(job_id)
        if not job:
            return None
        return job.get("output_files", {}).get(frame)


# Global default simulator store
farm_store = SimulatedRenderFarmStore()
