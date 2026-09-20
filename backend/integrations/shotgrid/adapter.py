"""
Autodesk ShotGrid / Flow Production Tracking Adapter.
Provides high-level helpers for AssetValidationAgent and MCP remediation tools,
transparently falling back to local asset repository fixtures when operating offline.
"""

import logging
from typing import Any, Optional

from backend.integrations.shotgrid.client import ShotGridRESTClient

logger = logging.getLogger(__name__)


class ShotGridAdapter:
    """
    Adapter orchestrating communication with Autodesk ShotGrid / Flow Production Tracking.
    Provides fallback simulation data when running in offline or test environments.
    """

    def __init__(
        self,
        custom_client: Optional[ShotGridRESTClient] = None,
    ) -> None:
        self.client = custom_client or ShotGridRESTClient()

    def is_live(self) -> bool:
        """True if client has credentials and endpoint configured."""
        return self.client.is_configured

    def is_healthy(self) -> bool:
        return self.client.is_healthy()

    def get_shot(
        self,
        project_name: Optional[str] = None,
        shot_code: str = "",
    ) -> Optional[dict[str, Any]]:
        """
        Retrieve shot cut in/out, sequence, and status.
        Falls back to standard editorial ranges (1001-1050) in offline mode.
        """
        if self.is_live():
            res = self.client.get_shot(project_name=project_name, shot_code=shot_code)
            if res:
                return res

        # Simulated fallback for tests and development
        if not shot_code:
            return None

        # Clean shot_code (e.g. SH001, SH042)
        code = shot_code.upper()
        return {
            "id": 1001,
            "code": code,
            "status": "ip",
            "sequence": "SQ010",
            "cut_in": 1001,
            "cut_out": 1050,
            "head_in": 993,
            "tail_out": 1058,
            "cut_duration": 50,
            "frame_range": "1001-1050",
            "description": f"Simulated ShotGrid shot record for {code}",
        }

    def get_published_file_versions(
        self,
        project_name: Optional[str] = None,
        entity_name: str = "",
        asset_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve published asset versions."""
        if self.is_live():
            res = self.client.get_published_file_versions(
                project_name=project_name,
                entity_name=entity_name,
                asset_type=asset_type,
            )
            if res:
                return res

        # Fallback to local asset store
        try:
            from backend.agents.asset_validation.mock_asset_repo import asset_repo
            asset = asset_repo.get_asset(entity_name)
            if asset:
                return [
                    {
                        "id": 5001,
                        "name": asset.asset_id,
                        "version_number": 1,
                        "path": asset.file_path,
                        "status": "apr" if asset.is_valid else "rev",
                    }
                ]
        except Exception:
            pass

        return []

    def update_shot_status(
        self,
        shot_id_or_code: str | int,
        new_status: str,
        note: Optional[str] = None,
    ) -> bool:
        """
        Update a shot's status in ShotGrid (e.g. to 'needs_fix' or 'td_hold').
        """
        if self.is_live():
            shot_id: Optional[int] = None
            if isinstance(shot_id_or_code, int) or str(shot_id_or_code).isdigit():
                shot_id = int(shot_id_or_code)
            else:
                shot_data = self.client.get_shot(shot_code=str(shot_id_or_code))
                if shot_data and shot_data.get("id"):
                    shot_id = int(shot_data["id"])

            if shot_id:
                return self.client.update_shot_status(shot_id, new_status, note=note)

        logger.info(
            "Simulated ShotGrid: Shot '%s' status updated to '%s' (note: %s)",
            shot_id_or_code,
            new_status,
            note,
        )
        return True


# Global default ShotGrid adapter singleton
shotgrid_adapter = ShotGridAdapter()
