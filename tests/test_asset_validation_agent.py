"""
Unit and integration tests for the VFX Asset Validation Specialist Agent.
Tests verify:
1. Scenario 1: Clean/Healthy Asset Graph (USD, Alembic, OpenVDB, UDIM textures intact)
2. Scenario 2: Broken USD References & Missing Sublayers (with dependency chain)
3. Scenario 3: Missing UDIM Textures (tile 1002 missing in sequence)
4. Scenario 4: Corrupted Alembic Archive (truncated 16-byte Ogawa header)
5. Scenario 5: Missing OpenVDB Grids & Missing Cache Frames (density grid & frame 1042)
6. Scenario 6: Incompatible Asset Version Mismatch (v001 vs approved v004)
7. Scenario 7: Cyclic Dependency Loop Containment (prevents recursion errors)
8. Scenario 8: Non-Existent Asset / Missing Record (strict zero invented evidence)
9. Scenario 9: Google ADK Supervisor Contract Integration (async investigate)
10. Scenario 10: Strict Read-Only Invariance (never modifies assets)
"""

import pytest

from backend.agents.asset_validation.agent import AssetValidationAgent
from backend.agents.asset_validation.tools import (
    check_dependencies,
    detect_missing_assets,
    detect_version_mismatch,
    validate_asset,
    validate_file_integrity,
)


@pytest.fixture
def asset_agent():
    return AssetValidationAgent()


# ── Scenario 1: Healthy Asset Graph ───────────────────────────────────────────

def test_scenario_1_healthy_asset_graph(asset_agent):
    """Scenario 1: Verifies all USD, ABC, VDB, and TX texture dependencies pass validation."""
    root_id = "asset_shot_clean"

    # 1. Direct tool tests
    val = validate_asset(root_id, store=asset_agent.store)
    assert val["available"] is True
    assert val["found"] is True
    assert val["is_valid"] is True
    assert val["asset_type"] == "USD"

    dep_res = check_dependencies(root_id, store=asset_agent.store)
    assert dep_res["available"] is True
    assert len(dep_res["missing_dependencies"]) == 0
    assert len(dep_res["corrupt_dependencies"]) == 0
    assert len(dep_res["cycles_detected"]) == 0
    assert len(dep_res["visited_asset_ids"]) >= 6

    miss_res = detect_missing_assets(root_id, store=asset_agent.store)
    assert miss_res["has_missing_assets"] is False

    ver_res = detect_version_mismatch(root_id, store=asset_agent.store)
    assert ver_res["has_mismatch"] is False

    integ = validate_file_integrity("/shows/PROJ/caches/char/hero/hero_anim_v003.abc", store=asset_agent.store)
    assert integ["is_intact"] is True
    assert integ["header_valid"] is True

    # 2. Agent full analysis
    report = asset_agent.analyze_asset(root_id)
    assert report.is_valid is True
    assert report.total_assets_inspected >= 6
    assert len(report.missing_asset_ids) == 0
    assert len(report.corrupt_asset_ids) == 0

    clean_finding = next(f for f in report.findings if f.finding_type == "ASSET_GRAPH_VALID")
    assert clean_finding.severity == "INFO"
    assert clean_finding.confidence >= 0.95
    assert len(clean_finding.dependency_chain) >= 6


# ── Scenario 2: Broken USD Reference & Missing Sublayer ──────────────────────

def test_scenario_2_broken_usd_reference(asset_agent):
    """Scenario 2: Detects missing sublayer sword_v002.usdc and isolates the dependency chain."""
    root_id = "asset_shot_broken_usd_ref"

    dep_res = check_dependencies(root_id, store=asset_agent.store)
    assert len(dep_res["missing_dependencies"]) >= 1
    missing = dep_res["missing_dependencies"][0]
    assert missing["asset_id"] == "asset_missing_sublayer_sword"
    assert "sword_v002.usdc" in missing["file_path"]

    report = asset_agent.analyze_asset(root_id)
    assert report.is_valid is False
    assert "asset_missing_sublayer_sword" in report.missing_asset_ids

    broken_finding = next(f for f in report.findings if f.finding_type == "BROKEN_USD_REFERENCE")
    assert broken_finding.severity == "CRITICAL"
    assert broken_finding.confidence >= 0.95
    assert "asset_missing_sublayer_sword" in broken_finding.asset_ids
    assert "asset_knight_stage" in broken_finding.asset_ids

    # Verify dependency chain includes root -> knight -> sword
    chain = broken_finding.dependency_chain
    assert "asset_shot_broken_usd_ref" in chain
    assert "asset_knight_stage" in chain
    assert "asset_missing_sublayer_sword" in chain


# ── Scenario 3: Missing UDIM Texture Tile ─────────────────────────────────────

def test_scenario_3_missing_udim_texture(asset_agent):
    """Scenario 3: Detects missing UDIM texture tile 1002 in lookdev asset."""
    root_id = "asset_shot_missing_udim"

    miss_res = detect_missing_assets(root_id, store=asset_agent.store)
    assert miss_res["has_missing_assets"] is True
    assert any("diffuse.1002.tx" in m.get("file_path", "") for m in miss_res["missing_assets"])

    report = asset_agent.analyze_asset(root_id)
    assert report.is_valid is False
    assert "asset_car_tex_1002" in report.missing_asset_ids

    tex_finding = next(f for f in report.findings if f.finding_type == "MISSING_TEXTURE_MAP")
    assert tex_finding.severity == "HIGH"
    assert tex_finding.confidence >= 0.95
    assert any("diffuse.1002.tx" in ev for ev in tex_finding.evidence)
    assert any("UDIM" in obs for obs in tex_finding.observed or tex_finding.evidence)


# ── Scenario 4: Corrupted Alembic Point Cache ─────────────────────────────────

def test_scenario_4_corrupted_alembic_cache(asset_agent):
    """Scenario 4: Detects truncated 16-byte Ogawa Alembic cache and invalid header."""
    file_path = "/shows/PROJ/caches/creature/dragon/dragon_anim_v001.abc"

    integ = validate_file_integrity(file_path, store=asset_agent.store)
    assert integ["is_intact"] is False
    assert integ["header_valid"] is False
    assert integ["file_size_bytes"] == 16
    assert "truncated" in integ["error_message"].lower()

    report = asset_agent.analyze_asset("asset_shot_corrupted_alembic")
    assert report.is_valid is False
    assert "asset_dragon_anim_corrupt" in report.corrupt_asset_ids

    corrupt_finding = next(f for f in report.findings if f.finding_type == "CORRUPTED_ASSET_DATA")
    assert corrupt_finding.severity == "CRITICAL"
    assert corrupt_finding.confidence >= 0.95
    assert any("16 bytes" in ev for ev in corrupt_finding.evidence)
    assert any("Ogawa" in obs for obs in corrupt_finding.observed)


# ── Scenario 5: Missing OpenVDB Grids & Frames ────────────────────────────────

def test_scenario_5_missing_vdb_grids_and_frames(asset_agent):
    """Scenario 5: Detects missing 'density' grid channel and frame 1042 sequence gap."""
    root_id = "asset_shot_missing_vdb"

    miss_res = detect_missing_assets(root_id, store=asset_agent.store)
    assert miss_res["has_missing_assets"] is True
    assert any("density" in m.get("reason", "") for m in miss_res["missing_assets"])
    assert any("1042" in m.get("reason", "") for m in miss_res["missing_assets"])

    report = asset_agent.analyze_asset(root_id)
    assert report.is_valid is False

    vdb_finding = next(f for f in report.findings if f.finding_type in ("MISSING_CACHE_FRAME_OR_GRID", "CORRUPTED_ASSET_DATA"))
    assert vdb_finding.confidence >= 0.95
    assert any("density" in ev.lower() or "grid" in ev.lower() for ev in vdb_finding.evidence)


# ── Scenario 6: Incompatible Asset Version Mismatch ───────────────────────────

def test_scenario_6_version_mismatch(asset_agent):
    """Scenario 6: Detects referenced asset version v001 incompatible with approved publish v004."""
    root_id = "asset_shot_version_mismatch"

    ver_res = detect_version_mismatch(root_id, store=asset_agent.store)
    assert ver_res["has_mismatch"] is True
    assert ver_res["mismatch_count"] >= 1
    mismatch = ver_res["mismatches"][0]
    assert mismatch["referenced_version"] == "v001"
    assert mismatch["expected_version"] == "v004"
    assert mismatch["is_incompatible"] is True

    report = asset_agent.analyze_asset(root_id)
    assert "asset_bridge_deprecated" in report.version_mismatches

    mismatch_finding = next(f for f in report.findings if f.finding_type == "INCOMPATIBLE_ASSET_VERSION")
    assert mismatch_finding.severity == "CRITICAL"
    assert mismatch_finding.confidence >= 0.95
    assert any("v001" in ev and "v004" in ev for ev in mismatch_finding.evidence)
    assert any("breaking" in ev.lower() for ev in mismatch_finding.evidence)


# ── Scenario 7: Circular Dependency Containment ───────────────────────────────

def test_scenario_7_circular_dependency_containment(asset_agent):
    """Scenario 7: Traversal terminates safely without infinite recursion on cyclic asset graphs."""
    root_id = "asset_shot_cyclic"

    dep_res = check_dependencies(root_id, store=asset_agent.store)
    assert len(dep_res["cycles_detected"]) >= 1

    report = asset_agent.analyze_asset(root_id)
    assert report.is_valid is False

    cycle_finding = next(f for f in report.findings if f.finding_type == "CYCLIC_DEPENDENCY_DETECTED")
    assert cycle_finding.severity == "CRITICAL"
    assert any("Circular" in ev for ev in cycle_finding.evidence)
    assert "asset_loop_a" in cycle_finding.asset_ids
    assert "asset_loop_b" in cycle_finding.asset_ids


# ── Scenario 8: Non-Existent Asset (Zero Invented Evidence) ───────────────────

def test_scenario_8_non_existent_asset_no_hallucination(asset_agent):
    """Scenario 8: Missing asset in catalog returns confidence 0.0 and zero invented evidence."""
    root_id = "asset_non_existent_ghost_999"

    # Tool returns found=False
    val = validate_asset(root_id, store=asset_agent.store)
    assert val["available"] is False
    assert val["found"] is False

    report = asset_agent.analyze_asset(root_id)
    assert report.is_valid is False
    assert report.overall_confidence == 0.0
    assert len(report.findings) == 1

    finding = report.findings[0]
    assert finding.finding_type == "ASSET_NOT_FOUND"
    assert finding.confidence == 0.0
    assert len(finding.evidence) == 0  # STRICT: Zero invented evidence
    assert len(finding.observed) == 0
    assert len(finding.unknown) >= 1


# ── Scenario 9: Google ADK Supervisor Contract Integration ───────────────────

@pytest.mark.asyncio
async def test_scenario_9_supervisor_integration_contract(asset_agent):
    """Scenario 9: Verifies that AssetValidationAgent satisfies the Google ADK BaseSpecialistAgent contract."""
    event = {
        "event_id": "evt-asset-001",
        "source": "shotgrid",
        "event_type": "ASSET_VALIDATION_FAILED",
        "asset_id": "asset_shot_broken_usd_ref",
        "entity": {
            "entity_type": "asset",
            "entity_id": "asset_shot_broken_usd_ref",
            "asset_name": "asset_shot_broken_usd_ref",
        },
    }
    specialist_report = await asset_agent.investigate("inc-asset-001", event)

    assert specialist_report.agent_name == "AssetValidationAgent"
    assert specialist_report.status == "SUCCESS"
    assert len(specialist_report.findings) >= 1
    assert len(specialist_report.evidence) >= 1
    assert len(specialist_report.hypotheses) >= 1

    first_finding = specialist_report.findings[0]
    assert first_finding.agent_name == "AssetValidationAgent"
    assert first_finding.category == "asset"
    assert first_finding.confidence >= 0.95
    assert "dependency_chain" in first_finding.details
    assert "asset_ids" in first_finding.details


# ── Scenario 10: Strict Read-Only Invariance ──────────────────────────────────

def test_scenario_10_agent_does_not_modify_assets(asset_agent):
    """Scenario 10: Strictly verifies agent only inspects and reports; never mutates asset store."""
    before_count = len(asset_agent.store.assets)
    before_state = {k: v.model_dump() for k, v in asset_agent.store.assets.items()}

    report = asset_agent.analyze_asset("asset_shot_broken_usd_ref")
    report_dict = report.model_dump()

    # Verify no mutation in store
    assert len(asset_agent.store.assets) == before_count
    after_state = {k: v.model_dump() for k, v in asset_agent.store.assets.items()}
    assert before_state == after_state

    # Verify no execution or modification keys in report
    assert "execute" not in report_dict
    assert "action" not in report_dict
    assert "remediation" not in report_dict
    assert "modify" not in report_dict
    assert "delete" not in report_dict
