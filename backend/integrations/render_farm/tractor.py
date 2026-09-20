"""
Pixar Tractor Engine API client.
Communicates with Pixar Tractor Engine (default port 8000) for jobs, blade tasks, and task logs.
"""

import logging
import os
from typing import Any, Optional
import httpx

from backend.integrations.render_farm.base import (
    BaseRenderFarmClient,
)

logger = logging.getLogger(__name__)


class TractorAPIClient(BaseRenderFarmClient):
    """
    Client for Pixar Tractor Engine REST API.
    Docs: https://renderman.pixar.com/resources/Tractor/tractor_api.html
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("TRACTOR_ENGINE_URL", "")
            or os.getenv("TRACTOR_API_URL", "")
        ).rstrip("/")
        self.user = user or os.getenv("TRACTOR_USER", "")
        self.password = password or os.getenv("TRACTOR_PASSWORD", "")
        self.timeout = timeout or float(os.getenv("TRACTOR_TIMEOUT", "10.0"))

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
            resp = self._client.get("/Tractor/monitor?q=version")
            return resp.status_code == 200
        except Exception:
            return False

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        if not self._client:
            return None
        try:
            resp = self._client.get(f"/Tractor/monitor?q=jdetails&jid={job_id}")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Error fetching Tractor job '%s': %s", job_id, e)
        return None

    def get_tasks(self, job_id: str) -> list[dict[str, Any]]:
        if not self._client:
            return []
        try:
            resp = self._client.get(f"/Tractor/monitor?q=tasks&jid={job_id}")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Error fetching Tractor tasks for '%s': %s", job_id, e)
        return []

    def get_task_reports(self, job_id: str, task_id: Optional[str] = None) -> list[dict[str, Any]]:
        if not self._client or not task_id:
            return []
        try:
            resp = self._client.get(f"/Tractor/monitor?q=tlog&jid={job_id}&tid={task_id}")
            if resp.status_code == 200:
                return [{"TaskID": task_id, "Log": resp.text}]
        except Exception as e:
            logger.warning("Error fetching Tractor logs for job '%s' task '%s': %s", job_id, task_id, e)
        return []

    def get_normalized_job(self, job_id: str) -> Optional[dict[str, Any]]:
        raw = self.get_job(job_id)
        if not raw:
            return None
        return {
            "job_id": job_id,
            "project": raw.get("project", "VFX_PROJECT"),
            "sequence": "SQ010",
            "shot": raw.get("title", "SH001"),
            "renderer": "renderman",
            "renderer_version": "26.1",
            "frame_range": "1001-1050",
            "status": "FAILED" if raw.get("stat") == "error" else "COMPLETED",
            "node_id": "blade-01",
            "frames": {},
            "output_files": {},
        }

    def requeue_job(self, job_id: str) -> bool:
        if not self._client:
            return False
        try:
            resp = self._client.get(f"/Tractor/queue?q=retry&jid={job_id}&user={self.user or 'vfx_td'}")
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Error requeuing Tractor job '%s': %s", job_id, e)
            return False

    def requeue_tasks(self, job_id: str, task_ids: list[str]) -> bool:
        if not self._client:
            return False
        try:
            tids = ",".join(task_ids)
            resp = self._client.get(f"/Tractor/queue?q=retry&jid={job_id}&tids={tids}&user={self.user or 'vfx_td'}")
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Error requeuing Tractor tasks for '%s': %s", job_id, e)
            return False
