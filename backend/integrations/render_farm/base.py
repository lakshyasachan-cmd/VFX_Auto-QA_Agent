"""
Base abstractions and schemas for VFX Render Farm Managers.
Defines unified interfaces for AWS Thinkbox Deadline, Pixar Tractor, and ASWF OpenCue.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class FarmStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    ACTIVE = "ACTIVE"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SUSPENDED = "SUSPENDED"


class FarmJobSummary(BaseModel):
    """Normalized summary of a render farm job across different farm managers."""
    job_id: str
    name: str = ""
    project: Optional[str] = None
    sequence: Optional[str] = None
    shot: Optional[str] = None
    user: Optional[str] = None
    pool: Optional[str] = None
    secondary_pool: Optional[str] = None
    renderer: Optional[str] = None
    renderer_version: Optional[str] = None
    dcc: Optional[str] = None
    frame_range: str = ""
    status: FarmStatus = FarmStatus.UNKNOWN
    node_id: Optional[str] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    frames: dict[int, dict[str, Any]] = Field(default_factory=dict)
    output_files: dict[int, Optional[dict[str, Any]]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseRenderFarmClient(ABC):
    """Abstract interface that all render farm clients must implement."""

    @abstractmethod
    def is_healthy(self) -> bool:
        """Check whether the farm manager API endpoint is reachable and responsive."""
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        """Retrieve raw job metadata directly from the farm REST/gRPC API."""
        pass

    @abstractmethod
    def get_tasks(self, job_id: str) -> list[dict[str, Any]]:
        """Retrieve task/frame execution records for a specific job."""
        pass

    @abstractmethod
    def get_task_reports(self, job_id: str, task_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Retrieve execution reports, error logs, and worker stdout/stderr for a job or task."""
        pass

    @abstractmethod
    def get_normalized_job(self, job_id: str) -> Optional[dict[str, Any]]:
        """
        Produce a normalized job record dict conforming to the schema expected by RenderQAAgent:
        {
            "job_id": str,
            "project": str,
            "sequence": str,
            "shot": str,
            "renderer": str,
            "renderer_version": str,
            "frame_range": str,
            "status": str,
            "node_id": str,
            "frames": { frame_num: { status, render_time, file_size, vram_peak_mb, exit_code, error_log } },
            "output_files": { frame_num: { path, size, nan_pixels, header_valid } }
        }
        """
        pass

    @abstractmethod
    def requeue_job(self, job_id: str) -> bool:
        """Re-queue a failed job in the farm manager."""
        pass

    @abstractmethod
    def requeue_tasks(self, job_id: str, task_ids: list[str]) -> bool:
        """Re-queue specific failed frames/tasks in the farm manager."""
        pass
