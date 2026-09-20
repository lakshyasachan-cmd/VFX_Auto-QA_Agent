"""
Unified Render Farm Adapter for VFX Mission Control.
Provides transparent routing between AWS Thinkbox Deadline, Pixar Tractor,
ASWF OpenCue, and the local simulated fallback store.
"""

import logging
import os
from typing import Any, Optional

from backend.integrations.render_farm.base import BaseRenderFarmClient
from backend.integrations.render_farm.deadline import DeadlineRESTClient
from backend.integrations.render_farm.opencue import OpenCueClient
from backend.integrations.render_farm.tractor import TractorAPIClient

logger = logging.getLogger(__name__)


class RenderFarmAdapter:
    """
    Production adapter orchestrating render farm manager connections.
    Routes live farm requests to the appropriate client (Deadline, Tractor, OpenCue),
    with seamless fallback to simulated farm store for testing.
    """

    def __init__(
        self,
        farm_type: Optional[str] = None,
        custom_client: Optional[BaseRenderFarmClient] = None,
        simulated_store: Optional[Any] = None,
    ) -> None:
        self._simulated_store = simulated_store
        self.farm_type = (farm_type or os.getenv("RENDER_FARM_TYPE", "auto")).lower()
        self._active_client: Optional[BaseRenderFarmClient] = custom_client

        if not self._active_client:
            self._init_client()

    @property
    def simulated_store(self) -> Any:
        if self._simulated_store is None:
            from backend.agents.render_qa.simulated_store import farm_store
            self._simulated_store = farm_store
        return self._simulated_store

    def _init_client(self) -> None:
        """Initialize active farm client according to configuration."""
        if self.farm_type == "deadline":
            self._active_client = DeadlineRESTClient()
        elif self.farm_type == "tractor":
            self._active_client = TractorAPIClient()
        elif self.farm_type == "opencue":
            self._active_client = OpenCueClient()
        elif self.farm_type == "simulated":
            self._active_client = None
        else:
            # Auto-detect based on configured environment URLs
            if os.getenv("DEADLINE_WS_URL") or os.getenv("DEADLINE_API_URL"):
                self._active_client = DeadlineRESTClient()
                self.farm_type = "deadline"
            elif os.getenv("TRACTOR_ENGINE_URL"):
                self._active_client = TractorAPIClient()
                self.farm_type = "tractor"
            elif os.getenv("OPENCUE_CUEBOT_URL"):
                self._active_client = OpenCueClient()
                self.farm_type = "opencue"
            else:
                self._active_client = None
                self.farm_type = "simulated"

    @property
    def active_client(self) -> Optional[BaseRenderFarmClient]:
        return self._active_client

    def is_live(self) -> bool:
        """True if connected to an external production render manager."""
        return self._active_client is not None and getattr(self._active_client, "is_configured", False)

    def register_job(self, job_id: str, data: dict[str, Any]) -> None:
        """Allow test suites to register simulated job scenarios."""
        self.simulated_store.register_job(job_id, data)

    def get_job_record(self, job_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve normalized job record from live farm client if available,
        falling back to the simulated farm store.
        """
        if self._active_client and getattr(self._active_client, "is_configured", False):
            try:
                live_record = self._active_client.get_normalized_job(job_id)
                if live_record:
                    return live_record
            except Exception as e:
                logger.warning("Live farm client error for job '%s': %s. Falling back to simulated store.", job_id, e)

        # Fallback to simulated store
        return self.simulated_store.get_job_record(job_id)

    def get_frame_record(self, job_id: str, frame: int) -> Optional[dict[str, Any]]:
        """Retrieve single frame execution telemetry."""
        record = self.get_job_record(job_id)
        if not record:
            return None
        frames = record.get("frames", {})
        return frames.get(frame)

    def get_frame_detail(self, job_id: str, frame: int) -> Optional[dict[str, Any]]:
        """Alias for get_frame_record."""
        return self.get_frame_record(job_id, frame)

    def get_output_file_telemetry(self, job_id: str, frame: int) -> Optional[dict[str, Any]]:
        """Retrieve single output frame inspection metadata."""
        record = self.get_job_record(job_id)
        if not record:
            return None
        output_files = record.get("output_files", {})
        return output_files.get(frame)

    def get_output_file(self, job_id: str, frame: int) -> Optional[dict[str, Any]]:
        """Alias for get_output_file_telemetry."""
        return self.get_output_file_telemetry(job_id, frame)

    def requeue_job(self, job_id: str) -> bool:
        """Re-queue a failed job in the active farm manager."""
        if self._active_client and getattr(self._active_client, "is_configured", False):
            return self._active_client.requeue_job(job_id)

        # In simulated mode, simulate successful requeue
        logger.info("Simulated farm: Job '%s' successfully requeued", job_id)
        return True

    def requeue_tasks(self, job_id: str, task_ids: list[str]) -> bool:
        """Re-queue specific failed frames in the active farm manager."""
        if self._active_client and getattr(self._active_client, "is_configured", False):
            return self._active_client.requeue_tasks(job_id, task_ids)

        logger.info("Simulated farm: Tasks %s for job '%s' successfully requeued", task_ids, job_id)
        return True


# Global default farm adapter instance
farm_adapter = RenderFarmAdapter()
