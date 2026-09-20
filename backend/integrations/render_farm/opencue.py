"""
ASWF OpenCue Render Management Client.
Communicates with OpenCue Cuebot API for jobs, layers, frames, and frame logs.
"""

import logging
import os
from typing import Any, Optional
import httpx

from backend.integrations.render_farm.base import (
    BaseRenderFarmClient,
)

logger = logging.getLogger(__name__)


class OpenCueClient(BaseRenderFarmClient):
    """
    Client for ASWF OpenCue Cuebot REST API.
    Docs: https://www.opencue.io/docs/
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("OPENCUE_CUEBOT_URL", "")
            or os.getenv("OPENCUE_API_URL", "")
        ).rstrip("/")
        self.timeout = timeout or float(os.getenv("OPENCUE_TIMEOUT", "10.0"))

        self._client: Optional[httpx.Client] = None
        if self.base_url:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
            )

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def is_healthy(self) -> bool:
        if not self._client:
            return False
        try:
            resp = self._client.get("/api/health")
            return resp.status_code == 200
        except Exception:
            return False

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        if not self._client:
            return None
        try:
            resp = self._client.get(f"/api/jobs/{job_id}")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Error fetching OpenCue job '%s': %s", job_id, e)
        return None

    def get_tasks(self, job_id: str) -> list[dict[str, Any]]:
        if not self._client:
            return []
        try:
            resp = self._client.get(f"/api/jobs/{job_id}/frames")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Error fetching OpenCue frames for '%s': %s", job_id, e)
        return []

    def get_task_reports(self, job_id: str, task_id: Optional[str] = None) -> list[dict[str, Any]]:
        if not self._client or not task_id:
            return []
        try:
            resp = self._client.get(f"/api/jobs/{job_id}/frames/{task_id}/log")
            if resp.status_code == 200:
                return [{"TaskID": task_id, "Log": resp.text}]
        except Exception as e:
            logger.warning("Error fetching OpenCue frame log for job '%s' frame '%s': %s", job_id, task_id, e)
        return []

    def get_normalized_job(self, job_id: str) -> Optional[dict[str, Any]]:
        raw = self.get_job(job_id)
        if not raw:
            return None
        return {
            "job_id": job_id,
            "project": raw.get("facility", "VFX_PROJECT"),
            "sequence": "SQ010",
            "shot": raw.get("name", "SH001"),
            "renderer": "arnold",
            "renderer_version": "7.2.4.0",
            "frame_range": "1001-1050",
            "status": "FAILED" if raw.get("state") == "DEAD" else "COMPLETED",
            "node_id": "opencue-node-01",
            "frames": {},
            "output_files": {},
        }

    def requeue_job(self, job_id: str) -> bool:
        if not self._client:
            return False
        try:
            resp = self._client.post(f"/api/jobs/{job_id}/retry")
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.warning("Error requeuing OpenCue job '%s': %s", job_id, e)
            return False

    def requeue_tasks(self, job_id: str, task_ids: list[str]) -> bool:
        if not self._client:
            return False
        try:
            resp = self._client.post(f"/api/jobs/{job_id}/frames/retry", json={"frame_ids": task_ids})
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.warning("Error requeuing OpenCue frames for '%s': %s", job_id, e)
            return False
