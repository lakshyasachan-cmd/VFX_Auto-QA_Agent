"""
Tests for AWS Thinkbox Deadline REST API client, Render Farm Adapter,
and RenderQAAgent integration.
"""

import pytest
from unittest.mock import MagicMock, patch
from backend.integrations.render_farm.deadline import DeadlineRESTClient
from backend.integrations.render_farm.adapter import RenderFarmAdapter
from backend.agents.render_qa.agent import RenderQAAgent


def test_deadline_log_analyzer_arnold_oom():
    """Test renderer log parsing for Arnold GPU Out-Of-Memory error."""
    client = DeadlineRESTClient(base_url="")
    log = (
        "00:02:00 24576MB ERROR   | [gpu] CUDA error: Out of memory while allocating 4096MB buffer.\n"
        "00:02:00 24576MB ERROR   | [gpu] Total VRAM available: 24576MB. Requested: 28672MB.\n"
        "00:02:01 24576MB FATAL   | Render process terminated with exit code 137 (SIGKILL / OOM)."
    )
    result = client.analyze_renderer_log(log)
    assert result["exit_code"] == 137
    assert result["error_type"] == "GPU_OUT_OF_MEMORY"
    assert result["vram_peak_mb"] == 24576.0
    assert "CUDA error" in result["matched_snippet"]


def test_deadline_log_analyzer_license_error():
    """Test log parsing for Arnold RLM license drop."""
    client = DeadlineRESTClient(base_url="")
    log = (
        "00:00:10   512MB ERROR   | [rlm] error: abort on license failure\n"
        "00:00:10   512MB FATAL   | Process exit code: 1"
    )
    result = client.analyze_renderer_log(log)
    assert result["exit_code"] == 1
    assert result["error_type"] == "LICENSE_ERROR"


def test_deadline_log_analyzer_vray_oom():
    """Test log parsing for V-Ray CUDA out of memory."""
    client = DeadlineRESTClient(base_url="")
    log = "[V-Ray] CUDA_ERROR_OUT_OF_MEMORY: out of memory on device 0 (NVIDIA RTX A6000)"
    result = client.analyze_renderer_log(log)
    assert result["exit_code"] == 137
    assert result["error_type"] == "GPU_OUT_OF_MEMORY"


def test_deadline_log_analyzer_nuke_enospc():
    """Test log parsing for disk space exhaustion during write."""
    client = DeadlineRESTClient(base_url="")
    log = "Write1: Cannot write to disk: No space left on device (ENOSPC)"
    result = client.analyze_renderer_log(log)
    assert result["exit_code"] == 28
    assert result["error_type"] == "DISK_FULL"


def test_deadline_normalization():
    """Test normalizing Deadline Web Service raw JSON responses into RenderQAAgent format."""
    client = DeadlineRESTClient(base_url="http://deadline-ws.test:8082")

    mock_job = {
        "Props": {
            "Name": "DUNE3_SQ010_SH042_lighting",
            "Batch": "DUNE3",
            "Plug": "Arnold",
            "Frames": "1001-1002",
            "Stat": 4,  # Failed
            "Comm": "Arnold 7.2.4.0",
        }
    }

    mock_tasks = [
        {
            "TaskID": 0,
            "Frames": "1001",
            "Stat": 3,  # Completed
            "Slave": "render-node-01",
            "Time": 320.0,
            "Errors": 0,
        },
        {
            "TaskID": 1,
            "Frames": "1002",
            "Stat": 4,  # Failed
            "Slave": "render-node-07",
            "Time": 45.0,
            "Errors": 1,
        },
    ]

    mock_reports = [
        {
            "TaskID": 1,
            "ReportType": "Error",
            "Log": (
                "00:00:45 24576MB ERROR | [gpu] CUDA error: Out of memory while allocating buffer.\n"
                "Process exit code: 137"
            ),
        }
    ]

    with patch.object(client, "get_job", return_value=mock_job):
        with patch.object(client, "get_tasks", return_value=mock_tasks):
            with patch.object(client, "get_task_reports", return_value=mock_reports):
                normalized = client.get_normalized_job("job-live-deadline-001")

    assert normalized is not None
    assert normalized["job_id"] == "job-live-deadline-001"
    assert normalized["project"] == "DUNE3"
    assert normalized["sequence"] == "SQ010"
    assert normalized["shot"] == "SH042"
    assert normalized["renderer"] == "arnold"
    assert normalized["status"] == "FAILED"
    assert normalized["node_id"] == "render-node-07"
    assert 1001 in normalized["frames"]
    assert normalized["frames"][1001]["status"] == "COMPLETED"
    assert normalized["frames"][1001]["exit_code"] == 0

    assert 1002 in normalized["frames"]
    assert normalized["frames"][1002]["status"] == "FAILED"
    assert normalized["frames"][1002]["exit_code"] == 137
    assert normalized["frames"][1002]["vram_peak_mb"] == 24576.0


def test_deadline_requeue_job():
    """Test Deadline job requeue endpoint dispatch."""
    client = DeadlineRESTClient(base_url="http://deadline-ws.test:8082")
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch.object(client._client, "put", return_value=mock_resp):
        success = client.requeue_job("job-deadline-999")
        assert success is True


def test_render_farm_adapter_fallback():
    """Test that RenderFarmAdapter falls back to simulated store when no live farm is reachable."""
    adapter = RenderFarmAdapter(farm_type="simulated")
    assert adapter.is_live() is False

    job = adapter.get_job_record("job_oom_arnold")
    assert job is not None
    assert job["job_id"] == "job_oom_arnold"
    assert job["renderer"] == "arnold"


def test_render_qa_agent_with_live_deadline_mock():
    """Test RenderQAAgent inspecting a job served by DeadlineRESTClient."""
    client = DeadlineRESTClient(base_url="http://deadline-ws.test:8082")

    mock_job = {
        "Props": {
            "Name": "SH001_comp_arnold",
            "Batch": "Avatar3",
            "Plug": "Arnold",
            "Frames": "1041-1042",
            "Stat": 4,
            "Comm": "Arnold 7.2.4.0",
        }
    }
    mock_tasks = [
        {
            "TaskID": 0,
            "Frames": "1041",
            "Stat": 3,
            "Slave": "render-node-42",
            "Time": 440.0,
            "Errors": 0,
        },
        {
            "TaskID": 1,
            "Frames": "1042",
            "Stat": 4,
            "Slave": "render-node-42",
            "Time": 120.0,
            "Errors": 1,
        },
    ]
    mock_reports = [
        {
            "TaskID": 1,
            "ReportType": "Error",
            "Log": (
                "00:02:00 24576MB ERROR | [gpu] CUDA error: Out of memory while allocating 4096MB buffer.\n"
                "00:02:00 24576MB ERROR | [gpu] Total VRAM available: 24576MB. Requested: 28672MB.\n"
                "00:02:01 24576MB FATAL | Render process terminated with exit code 137 (SIGKILL / OOM)."
            ),
        }
    ]

    with patch.object(client, "get_job", return_value=mock_job):
        with patch.object(client, "get_tasks", return_value=mock_tasks):
            with patch.object(client, "get_task_reports", return_value=mock_reports):
                adapter = RenderFarmAdapter(custom_client=client)
                agent = RenderQAAgent(store=adapter)
                report = agent.analyze_job("job-deadline-oom-01")

    assert report.job_id == "job-deadline-oom-01"
    assert len(report.findings) >= 1
    oom_findings = [f for f in report.findings if f.finding_type == "GPU_OUT_OF_MEMORY"]
    assert len(oom_findings) == 1
    assert oom_findings[0].confidence >= 0.95
    assert "CUDA Out-Of-Memory" in oom_findings[0].description
