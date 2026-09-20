"""
Production Autodesk ShotGrid / Flow Production Tracking REST API v1 Client.
Supports:
- OAuth2 Client Credentials authentication with automatic token renewal and caching
- Querying Shot metadata, sequence associations, cut in/out frames, and assigned artists
- Inspecting Published File entities, cache versions (USD, Alembic, OpenVDB), and review statuses
- Bidirectional status updates (e.g. flagging a shot to 'needs_fix' or 'td_hold')
- Creating diagnostic QA Notes linked to published asset versions
"""

import logging
import os
import time
from typing import Any, Optional
import httpx

logger = logging.getLogger(__name__)


class ShotGridRESTClient:
    """
    Client for Autodesk ShotGrid (Flow Production Tracking) REST API v1.
    Docs: https://developer.shotgridsoftware.com/rest-api/
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        script_name: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        verify_ssl: bool = True,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("SHOTGRID_URL", "")
            or os.getenv("SHOTGRID_INSTANCE_URL", "")
        ).rstrip("/")
        self.script_name = script_name or os.getenv("SHOTGRID_SCRIPT_NAME", "")
        self.api_key = api_key or os.getenv("SHOTGRID_API_KEY", "")
        self.timeout = timeout or float(os.getenv("SHOTGRID_TIMEOUT", "10.0"))
        self.verify_ssl = verify_ssl

        # Token caching
        self._access_token: Optional[str] = None
        self._token_expiry_timestamp: float = 0.0

        self._client = httpx.Client(
            base_url=self.base_url if self.base_url else "https://localhost",
            timeout=self.timeout,
            verify=self.verify_ssl,
        )

    @property
    def is_configured(self) -> bool:
        """Returns True if minimum required credentials and endpoint are present."""
        return bool(self.base_url and self.script_name and self.api_key)

    def _get_valid_token(self) -> Optional[str]:
        """
        Authenticate via OAuth2 Client Credentials grant (POST /api/v1/auth/access_token).
        Caches and automatically refreshes the bearer token before expiration.
        """
        now = time.time()
        # Return cached token if valid for at least 60 more seconds
        if self._access_token and now < (self._token_expiry_timestamp - 60):
            return self._access_token

        if not self.is_configured:
            return None

        try:
            token_url = f"{self.base_url}/api/v1/auth/access_token"
            data = {
                "client_id": self.script_name,
                "client_secret": self.api_key,
                "grant_type": "client_credentials",
            }
            resp = self._client.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code == 200:
                payload = resp.json()
                self._access_token = payload.get("access_token")
                expires_in = float(payload.get("expires_in", 3600))
                self._token_expiry_timestamp = now + expires_in
                logger.debug("Obtained new ShotGrid access token; expires in %s seconds", expires_in)
                return self._access_token
            else:
                logger.warning("ShotGrid auth failed with HTTP %d: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Error requesting ShotGrid access token: %s", e)

        return None

    def _auth_headers(self) -> dict[str, str]:
        """Build headers with the current valid Bearer token."""
        token = self._get_valid_token()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "VFX-AutoQA-MissionControl/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def is_healthy(self) -> bool:
        """Check whether the ShotGrid REST API endpoint is responsive and reachable."""
        if not self.is_configured:
            return False
        try:
            headers = self._auth_headers()
            if "Authorization" not in headers:
                return False
            resp = self._client.get(f"{self.base_url}/api/v1/schema/entities", headers=headers)
            return resp.status_code == 200
        except Exception:
            return False

    def get_shot(
        self,
        project_name: Optional[str] = None,
        shot_code: str = "",
    ) -> Optional[dict[str, Any]]:
        """
        Query Shot entity by code and optional project name.
        Retrieves sequence, cut in/out frames, head/tail handles, status, and assigned artists.
        """
        if not self.is_configured or not shot_code:
            return None

        headers = self._auth_headers()
        if "Authorization" not in headers:
            return None

        try:
            filters = [["code", "is", shot_code]]
            if project_name:
                filters.append(["project.Project.name", "is", project_name])

            payload = {
                "filters": filters,
                "fields": [
                    "code",
                    "description",
                    "sg_status_list",
                    "sg_sequence",
                    "sg_cut_in",
                    "sg_cut_out",
                    "sg_head_in",
                    "sg_tail_out",
                    "sg_cut_duration",
                    "project",
                    "task_assignees",
                ],
            }
            resp = self._client.post(
                f"{self.base_url}/api/v1/entity/shots/_search",
                json=payload,
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    raw = data[0]
                    attrs = raw.get("attributes", {})
                    rel = raw.get("relationships", {})

                    seq_data = rel.get("sg_sequence", {}).get("data")
                    sequence_name = seq_data.get("name") if seq_data else None

                    cut_in = attrs.get("sg_cut_in") or 1001
                    cut_out = attrs.get("sg_cut_out") or 1050
                    cut_duration = attrs.get("sg_cut_duration") or (cut_out - cut_in + 1)

                    return {
                        "id": raw.get("id"),
                        "code": attrs.get("code", shot_code),
                        "status": attrs.get("sg_status_list", "ip"),
                        "sequence": sequence_name or "SQ010",
                        "cut_in": int(cut_in),
                        "cut_out": int(cut_out),
                        "head_in": int(attrs.get("sg_head_in") or (cut_in - 8)),
                        "tail_out": int(attrs.get("sg_tail_out") or (cut_out + 8)),
                        "cut_duration": int(cut_duration),
                        "frame_range": f"{cut_in}-{cut_out}",
                        "description": attrs.get("description", ""),
                    }
            else:
                logger.warning("ShotGrid get_shot error HTTP %d: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Error fetching ShotGrid shot '%s': %s", shot_code, e)

        return None

    def get_published_file_versions(
        self,
        project_name: Optional[str] = None,
        entity_name: str = "",
        asset_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Query published file versions (USD, Alembic, OpenVDB caches, EXR plates)
        associated with a shot or asset.
        """
        if not self.is_configured or not entity_name:
            return []

        headers = self._auth_headers()
        if "Authorization" not in headers:
            return []

        try:
            filters = [
                ["entity.Shot.code", "is", entity_name],
            ]
            if asset_type:
                filters.append(["published_file_type.PublishedFileType.code", "is", asset_type])

            payload = {
                "filters": filters,
                "fields": [
                    "code",
                    "name",
                    "version_number",
                    "path",
                    "published_file_type",
                    "sg_status_list",
                    "created_at",
                ],
            }
            resp = self._client.post(
                f"{self.base_url}/api/v1/entity/published_files/_search",
                json=payload,
                headers=headers,
            )
            if resp.status_code == 200:
                items = resp.json().get("data", [])
                results = []
                for item in items:
                    attrs = item.get("attributes", {})
                    path_obj = attrs.get("path", {})
                    path_str = path_obj.get("local_path") or path_obj.get("url") or ""
                    results.append({
                        "id": item.get("id"),
                        "name": attrs.get("name") or attrs.get("code"),
                        "version_number": attrs.get("version_number", 1),
                        "path": path_str,
                        "status": attrs.get("sg_status_list", "act"),
                        "created_at": attrs.get("created_at"),
                    })
                return results
            else:
                logger.warning("ShotGrid get_published_file_versions HTTP %d: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Error fetching published file versions for '%s': %s", entity_name, e)

        return []

    def update_shot_status(
        self,
        shot_id: int,
        new_status: str,
        note: Optional[str] = None,
    ) -> bool:
        """
        Update a Shot's pipeline status (e.g. 'needs_fix', 'td_hold', 'apr', 'wtg').
        Optionally attaches a QA diagnosis note to the shot.
        """
        if not self.is_configured:
            return False

        headers = self._auth_headers()
        if "Authorization" not in headers:
            return False

        try:
            payload = {"sg_status_list": new_status}
            resp = self._client.put(
                f"{self.base_url}/api/v1/entity/shots/{shot_id}",
                json=payload,
                headers=headers,
            )
            if resp.status_code in (200, 204):
                logger.info("Updated ShotGrid shot %s status to '%s'", shot_id, new_status)
                if note:
                    self.create_version_note(shot_id, note, entity_type="Shot")
                return True
            else:
                logger.warning("Failed to update ShotGrid shot %s status HTTP %d: %s", shot_id, resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Error updating ShotGrid shot status: %s", e)

        return False

    def create_version_note(
        self,
        entity_id: int,
        note_text: str,
        entity_type: str = "Version",
    ) -> bool:
        """Attach a diagnostic QA investigation note to a ShotGrid entity."""
        if not self.is_configured or not note_text:
            return False

        headers = self._auth_headers()
        if "Authorization" not in headers:
            return False

        try:
            payload = {
                "subject": "Automated VFX QA Diagnostic Notice",
                "content": note_text,
                "note_links": [{"type": entity_type, "id": entity_id}],
            }
            resp = self._client.post(
                f"{self.base_url}/api/v1/entity/notes",
                json=payload,
                headers=headers,
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning("Error creating ShotGrid note: %s", e)
            return False
