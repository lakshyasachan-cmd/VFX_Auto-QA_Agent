"""
Tests for Autodesk ShotGrid / Flow Production Tracking REST API client,
ShotGrid Adapter, and AssetValidationAgent editorial cut range verification.
"""

import pytest
from unittest.mock import MagicMock, patch
from backend.integrations.shotgrid.client import ShotGridRESTClient
from backend.integrations.shotgrid.adapter import ShotGridAdapter
from backend.agents.asset_validation.agent import AssetValidationAgent
from backend.agents.asset_validation.tools import validate_shot_cut_range


def test_shotgrid_token_authentication_and_caching():
    """Test OAuth2 client credentials token authentication and caching."""
    client = ShotGridRESTClient(
        base_url="https://test.shotgrid.autodesk.com",
        script_name="vfx_test_agent",
        api_key="secret_test_key",
    )

    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {
        "access_token": "mock_jwt_token_12345",
        "token_type": "Bearer",
        "expires_in": 3600,
    }

    with patch.object(client._client, "post", return_value=mock_token_resp) as mock_post:
        token = client._get_valid_token()
        assert token == "mock_jwt_token_12345"
        assert client._access_token == "mock_jwt_token_12345"
        mock_post.assert_called_once()

        # Second call should return cached token without making another POST request
        token_cached = client._get_valid_token()
        assert token_cached == "mock_jwt_token_12345"
        assert mock_post.call_count == 1


def test_shotgrid_get_shot_metadata():
    """Test querying Shot entity with cut in/out frames and sequence."""
    client = ShotGridRESTClient(
        base_url="https://test.shotgrid.autodesk.com",
        script_name="vfx_test_agent",
        api_key="secret_test_key",
    )
    client._access_token = "mock_token"
    client._token_expiry_timestamp = 9999999999.0

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 200
    mock_search_resp.json.return_value = {
        "data": [
            {
                "id": 402,
                "attributes": {
                    "code": "SH001",
                    "sg_status_list": "ip",
                    "sg_cut_in": 1001,
                    "sg_cut_out": 1050,
                    "sg_head_in": 993,
                    "sg_tail_out": 1058,
                    "sg_cut_duration": 50,
                    "description": "Hero flying through canyon",
                },
                "relationships": {
                    "sg_sequence": {
                        "data": {"id": 10, "name": "SQ010", "type": "Sequence"}
                    }
                },
            }
        ]
    }

    with patch.object(client._client, "post", return_value=mock_search_resp):
        shot = client.get_shot(project_name="Avatar3", shot_code="SH001")

    assert shot is not None
    assert shot["id"] == 402
    assert shot["code"] == "SH001"
    assert shot["sequence"] == "SQ010"
    assert shot["cut_in"] == 1001
    assert shot["cut_out"] == 1050
    assert shot["cut_duration"] == 50


def test_shotgrid_get_published_file_versions():
    """Test querying published files for a shot."""
    client = ShotGridRESTClient(
        base_url="https://test.shotgrid.autodesk.com",
        script_name="vfx_test_agent",
        api_key="secret_test_key",
    )
    client._access_token = "mock_token"
    client._token_expiry_timestamp = 9999999999.0

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {
                "id": 901,
                "attributes": {
                    "code": "hero_env_geo_v003",
                    "version_number": 3,
                    "path": {"local_path": "/shows/AV3/shots/SH001/publish/hero_env.usd"},
                    "sg_status_list": "apr",
                    "created_at": "2026-09-18T10:00:00Z",
                },
            }
        ]
    }

    with patch.object(client._client, "post", return_value=mock_resp):
        publishes = client.get_published_file_versions(entity_name="SH001")

    assert len(publishes) == 1
    assert publishes[0]["name"] == "hero_env_geo_v003"
    assert publishes[0]["version_number"] == 3
    assert publishes[0]["status"] == "apr"
    assert "/shows/AV3/shots/SH001/publish/hero_env.usd" in publishes[0]["path"]


def test_shotgrid_update_shot_status():
    """Test updating shot status to needs_fix."""
    client = ShotGridRESTClient(
        base_url="https://test.shotgrid.autodesk.com",
        script_name="vfx_test_agent",
        api_key="secret_test_key",
    )
    client._access_token = "mock_token"
    client._token_expiry_timestamp = 9999999999.0

    mock_put = MagicMock()
    mock_put.status_code = 200

    with patch.object(client._client, "put", return_value=mock_put):
        success = client.update_shot_status(shot_id=402, new_status="needs_fix")
        assert success is True


def test_shotgrid_adapter_fallback_when_offline():
    """Test that ShotGridAdapter gracefully falls back to simulated shot data when offline."""
    client = ShotGridRESTClient(base_url="")
    adapter = ShotGridAdapter(custom_client=client)

    assert adapter.is_live() is False
    shot = adapter.get_shot(shot_code="SH042")
    assert shot is not None
    assert shot["code"] == "SH042"
    assert shot["cut_in"] == 1001
    assert shot["cut_out"] == 1050
    assert shot["frame_range"] == "1001-1050"


def test_validate_shot_cut_range_tool():
    """Test tool function validate_shot_cut_range comparing actual frames against ShotGrid."""
    adapter = ShotGridAdapter(custom_client=ShotGridRESTClient(base_url=""))
    # Shot cut range is 1001-1050 (50 frames)
    # Give it 1001-1040 (missing 1041-1050)
    available_frames = list(range(1001, 1041))
    result = validate_shot_cut_range("SH001", available_frames=available_frames, shotgrid=adapter)

    assert result["available"] is True
    assert result["is_complete"] is False
    assert result["total_cut_frames"] == 50
    assert result["covered_frames"] == 40
    assert result["coverage_pct"] == 80.0
    assert result["missing_frames"] == list(range(1041, 1051))


def test_asset_validation_agent_detects_missing_editorial_frames():
    """Test that AssetValidationAgent detects missing frames when an asset fails to cover the ShotGrid cut."""
    adapter = ShotGridAdapter(custom_client=ShotGridRESTClient(base_url=""))
    agent = AssetValidationAgent(shotgrid=adapter)

    # Valid root asset: asset_shot_clean
    # Context says frame_range is 1001-1035, while ShotGrid cut is 1001-1050
    ctx = {
        "shot": "SH001",
        "frame_range": "1001-1035",
        "project": "Avatar3",
    }
    report = agent.analyze_asset("asset_shot_clean", context=ctx)

    cut_findings = [f for f in report.findings if f.finding_type == "MISSING_CUT_RANGE_FRAMES"]
    assert len(cut_findings) == 1
    assert cut_findings[0].severity == "CRITICAL"
    assert cut_findings[0].confidence == 0.98
    assert "Missing 15 frames" in cut_findings[0].evidence[1]
