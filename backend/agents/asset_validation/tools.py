"""
Asset validation inspection tools for USD, Alembic, OpenVDB, and EXR textures.
Functions:
1. validate_asset(asset_id)
2. check_dependencies(asset_id, depth)
3. detect_missing_assets(asset_id)
4. detect_version_mismatch(asset_id, target_version)
5. validate_file_integrity(file_path)

STRICT RULES:
- The agent and tools MUST NEVER modify assets or files (read-only inspection).
- Never claim an asset exists or has dependencies if not supplied in the catalog.
- Protects against cycles and infinite loops.
"""

import os
from typing import Any, Optional
from backend.agents.asset_validation.mock_asset_repo import (
    AssetRepositoryStore,
    asset_repo,
)
from backend.agents.asset_validation.schemas import (
    FileIntegrityResult,
)

# Recognized VFX magic byte signatures
VFX_MAGIC_SIGNATURES = {
    b"VDB ": "OpenVDB",
    b"\x76\x2f\x31\x01": "OpenEXR",
    b"Ogawa": "Alembic Ogawa",
    b"\x89HDF": "Alembic HDF5",
    b"#usda": "USD Text",
    b"PXR-USDC": "USD Crate Binary",
    b"\x89PNG": "PNG",
    b"II*\x00": "TIFF Little-Endian",
    b"MM\x00*": "TIFF Big-Endian",
    b"\xff\xd8\xff": "JPEG",
}


def inspect_physical_file(file_path: str) -> Optional[dict[str, Any]]:
    """Inspect a physical file on the local filesystem or mounted NAS storage."""
    if not os.path.exists(file_path):
        return None
    try:
        stat = os.stat(file_path)
        size = stat.st_size
        header_valid = False
        format_detected = "Unknown"
        err_msg = None

        if size == 0:
            err_msg = "0-byte file length"
        elif size < 4:
            err_msg = f"Truncated file: size is only {size} bytes"
        else:
            with open(file_path, "rb") as f:
                header = f.read(16)
            for magic, fmt in VFX_MAGIC_SIGNATURES.items():
                if header.startswith(magic):
                    header_valid = True
                    format_detected = fmt
                    break
            if not header_valid and size > 32:
                # If size is sufficient and file readable, header is treated as valid generic format
                header_valid = True
                format_detected = "Generic Binary/Text"

        is_intact = (size > 0) and (err_msg is None)
        return {
            "exists": True,
            "file_size_bytes": size,
            "is_intact": is_intact,
            "header_valid": header_valid,
            "format": format_detected,
            "error_message": err_msg,
        }
    except Exception as exc:
        return {
            "exists": True,
            "file_size_bytes": 0,
            "is_intact": False,
            "header_valid": False,
            "format": "Error",
            "error_message": f"Filesystem permission/I/O error: {exc}",
        }


def validate_asset(
    asset_id: str,
    store: Optional[AssetRepositoryStore] = None,
) -> dict[str, Any]:
    """
    Validates a primary asset record in the repository.
    Inspects existence, file path, disk presence, corruption flag, and metadata.
    Supports real on-disk files as well as simulated catalog records.
    """
    # 1. Check if asset_id is a real physical file on disk/NAS
    if os.path.exists(asset_id):
        p_info = inspect_physical_file(asset_id)
        if p_info:
            ext = os.path.splitext(asset_id)[1].lstrip(".").upper() or "UNKNOWN"
            issues = [p_info["error_message"]] if p_info["error_message"] else []
            return {
                "available": True,
                "found": True,
                "asset_id": os.path.basename(asset_id),
                "file_path": os.path.abspath(asset_id),
                "asset_type": ext,
                "version": "live_disk",
                "expected_version": "live_disk",
                "file_size_bytes": p_info["file_size_bytes"],
                "exists_on_disk": True,
                "is_corrupted": not p_info["is_intact"],
                "corruption_reason": p_info["error_message"],
                "is_valid": p_info["is_intact"],
                "issues": issues,
                "dependencies": [],
                "metadata": {"format": p_info["format"], "real_filesystem": True},
            }

    # 2. Query repository store
    s = store or asset_repo
    node = s.get_asset(asset_id)
    if not node:
        return {
            "available": False,
            "found": False,
            "asset_id": asset_id,
            "reason": f"Asset '{asset_id}' not found in studio asset repository.",
        }

    is_valid = node.exists_on_disk and not node.is_corrupted and node.file_size_bytes > 0
    issues: list[str] = []
    if not node.exists_on_disk:
        issues.append("File does not exist on storage mount")
    if node.is_corrupted:
        issues.append(node.corruption_reason or "Asset marked corrupted")
    if node.file_size_bytes == 0:
        issues.append("0-byte file length")

    return {
        "available": True,
        "found": True,
        "asset_id": node.asset_id,
        "file_path": node.file_path,
        "asset_type": node.asset_type.value,
        "version": node.version,
        "expected_version": node.expected_version,
        "file_size_bytes": node.file_size_bytes,
        "exists_on_disk": node.exists_on_disk,
        "is_corrupted": node.is_corrupted,
        "corruption_reason": node.corruption_reason,

        "is_valid": is_valid,
        "issues": issues,
        "dependencies": node.dependencies,
        "metadata": node.metadata,
    }


def check_dependencies(
    asset_id: str,
    depth: int = 10,
    store: Optional[AssetRepositoryStore] = None,
) -> dict[str, Any]:
    """
    Traverses the full dependency tree starting from asset_id up to specified depth.
    Detects missing referenced assets, corrupted sub-assets, circular dependency loops,
    and builds an ordered linear dependency chain.
    """
    s = store or asset_repo
    root_node = s.get_asset(asset_id)
    if not root_node:
        return {
            "available": False,
            "found": False,
            "root_asset_id": asset_id,
            "reason": f"Root asset '{asset_id}' not found in repository.",
        }

    visited: set[str] = set()
    chain: list[str] = []
    missing_deps: list[dict[str, Any]] = []
    corrupt_deps: list[dict[str, Any]] = []
    graph: dict[str, list[str]] = {}
    cycles: list[list[str]] = []

    def _traverse(current_id: str, current_path: list[str], current_depth: int) -> None:
        if current_depth > depth:
            return

        if current_id in current_path:
            # Cycle detected
            cycle_loop = current_path[current_path.index(current_id):] + [current_id]
            cycles.append(cycle_loop)
            return

        current_path.append(current_id)
        if current_id not in visited:
            visited.add(current_id)
            chain.append(current_id)

        node = s.get_asset(current_id)
        if not node:
            missing_deps.append({
                "asset_id": current_id,
                "file_path": None,
                "referenced_by": current_path[-2] if len(current_path) >= 2 else root_asset_id,
                "reason": f"Referenced asset '{current_id}' does not exist in repository catalog.",
            })
            current_path.pop()
            return

        if not node.exists_on_disk:
            missing_deps.append({
                "asset_id": node.asset_id,
                "file_path": node.file_path,
                "referenced_by": current_path[-2] if len(current_path) >= 2 else root_asset_id,
                "reason": node.corruption_reason or f"File '{node.file_path}' missing from storage disk (ENOENT).",
            })

        if node.is_corrupted:
            corrupt_deps.append({
                "asset_id": node.asset_id,
                "file_path": node.file_path,
                "referenced_by": current_path[-2] if len(current_path) >= 2 else root_asset_id,
                "reason": node.corruption_reason or "Archive header or data block corrupted.",
            })

        graph[current_id] = list(node.dependencies)
        for child_id in node.dependencies:
            _traverse(child_id, list(current_path), current_depth + 1)

    root_asset_id = asset_id
    _traverse(asset_id, [], 0)

    return {
        "available": True,
        "found": True,
        "root_asset_id": asset_id,
        "total_dependencies": len(visited) - 1 if asset_id in visited else len(visited),
        "visited_asset_ids": list(visited),
        "missing_dependencies": missing_deps,
        "corrupt_dependencies": corrupt_deps,
        "dependency_chain": chain,
        "dependency_graph": graph,
        "cycles_detected": cycles,
    }


def detect_missing_assets(
    asset_id: str,
    store: Optional[AssetRepositoryStore] = None,
) -> dict[str, Any]:
    """
    Examines an asset and its downstream dependencies specifically for missing files,
    broken USD composition references, missing UDIM texture tiles, or cache frame sequence gaps.
    """
    dep_res = check_dependencies(asset_id, depth=10, store=store)
    if not dep_res.get("available"):
        return dep_res

    missing_list = dep_res.get("missing_dependencies", [])

    # Check for missing cache frames or missing VDB grids in visited assets
    s = store or asset_repo
    for vid in dep_res.get("visited_asset_ids", []):
        node = s.get_asset(vid)
        if node and node.metadata:
            missing_frames = node.metadata.get("missing_frames", [])
            if missing_frames:
                missing_list.append({
                    "asset_id": node.asset_id,
                    "file_path": node.file_path,
                    "referenced_by": asset_id,
                    "reason": f"Missing frame cache files for frames: {missing_frames}",
                })
            missing_grids = [
                g for g in node.metadata.get("required_grids", [])
                if g not in node.metadata.get("available_grids", [])
            ]
            if missing_grids:
                missing_list.append({
                    "asset_id": node.asset_id,
                    "file_path": node.file_path,
                    "referenced_by": asset_id,
                    "reason": f"Missing required OpenVDB grid channels: {missing_grids}",
                })

    return {
        "available": True,
        "found": True,
        "asset_id": asset_id,
        "has_missing_assets": len(missing_list) > 0,
        "missing_assets": missing_list,
        "missing_count": len(missing_list),
        "dependency_chain": dep_res.get("dependency_chain", []),
    }


def detect_version_mismatch(
    asset_id: str,
    target_version: Optional[str] = None,
    store: Optional[AssetRepositoryStore] = None,
) -> dict[str, Any]:
    """
    Audits an asset and all referenced dependencies for version discrepancies
    against published release standards or target project tags.
    """
    dep_res = check_dependencies(asset_id, depth=10, store=store)
    if not dep_res.get("available"):
        return dep_res

    s = store or asset_repo
    mismatches: list[dict[str, Any]] = []

    for vid in dep_res.get("visited_asset_ids", []):
        node = s.get_asset(vid)
        if not node:
            continue

        expected = node.expected_version
        if vid == asset_id and target_version:
            expected = target_version

        is_mismatched = False
        is_incompatible = False
        details = "Version matches expected publish"

        if expected and node.version != expected:
            is_mismatched = True
            is_incompatible = node.metadata.get("is_incompatible", False)
            breaking = node.metadata.get("breaking_change")
            details = f"Referenced version '{node.version}' does not match expected '{expected}'"
            if breaking:
                details += f". Breaking incompatibility: {breaking}"

        if is_mismatched:
            mismatches.append({
                "asset_id": node.asset_id,
                "file_path": node.file_path,
                "referenced_version": node.version,
                "expected_version": expected,
                "is_mismatched": is_mismatched,
                "is_incompatible": is_incompatible,
                "details": details,
            })

    return {
        "available": True,
        "found": True,
        "asset_id": asset_id,
        "has_mismatch": len(mismatches) > 0,
        "mismatches": mismatches,
        "mismatch_count": len(mismatches),
    }


def validate_file_integrity(
    file_path: str,
    store: Optional[AssetRepositoryStore] = None,
) -> dict[str, Any]:
    """
    Inspects physical file integrity, magic header validity, and byte sizes for an asset.
    Supports real physical filesystem and mounted NAS storage, as well as simulated catalog assets.
    """
    # 1. Inspect real physical file on disk/NAS if it exists
    if os.path.exists(file_path):
        p_info = inspect_physical_file(file_path)
        if p_info:
            result = FileIntegrityResult(
                file_path=os.path.abspath(file_path),
                asset_id=os.path.basename(file_path),
                exists=p_info["exists"],
                is_intact=p_info["is_intact"],
                file_size_bytes=p_info["file_size_bytes"],
                header_valid=p_info["header_valid"],
                error_message=p_info["error_message"],
            )
            dump = result.model_dump(mode="json")
            dump["available"] = True
            dump["found"] = True
            dump["real_filesystem"] = True
            dump["format_detected"] = p_info["format"]
            return dump

    # 2. Check catalog store
    s = store or asset_repo
    node = s.get_asset_by_path(file_path)

    if not node:
        return {
            "available": False,
            "found": False,
            "file_path": file_path,
            "reason": f"File path '{file_path}' is not registered in asset catalog and not found on disk.",
        }

    header_valid = node.file_size_bytes > 32 and not node.is_corrupted
    is_intact = node.exists_on_disk and not node.is_corrupted and header_valid

    err_msg = None
    if not node.exists_on_disk:
        err_msg = "File does not exist on storage mount"
    elif node.is_corrupted:
        err_msg = node.corruption_reason or "Archive header corrupted"
    elif node.file_size_bytes <= 32:
        err_msg = f"Truncated file: size is only {node.file_size_bytes} bytes"

    result = FileIntegrityResult(
        file_path=file_path,
        asset_id=node.asset_id,
        exists=node.exists_on_disk,
        is_intact=is_intact,
        file_size_bytes=node.file_size_bytes,
        header_valid=header_valid,
        error_message=err_msg,
    )
    dump = result.model_dump(mode="json")
    dump["available"] = True
    dump["found"] = True
    return dump


def validate_shot_cut_range(
    shot_code: str,
    available_frames: Any,
    project: Optional[str] = None,
    shotgrid: Optional[Any] = None,
) -> dict[str, Any]:
    """
    Tool 6: Validates whether a published frame sequence or cache covers the official
    Autodesk ShotGrid / Flow Production Tracking editorial cut in/out range.
    """
    if shotgrid is None:
        try:
            from backend.integrations.shotgrid.adapter import shotgrid_adapter
            sg = shotgrid_adapter
        except ImportError:
            sg = None
    else:
        sg = shotgrid

    shot_info = sg.get_shot(project_name=project, shot_code=shot_code) if sg else None
    if not shot_info:
        return {
            "available": False,
            "shot_code": shot_code,
            "reason": f"Shot '{shot_code}' not found in ShotGrid database",
        }

    cut_in = int(shot_info.get("cut_in", 1001))
    cut_out = int(shot_info.get("cut_out", 1050))
    expected_frames = set(range(cut_in, cut_out + 1))
    actual_frames = set(available_frames) if available_frames is not None else set()

    missing = sorted(list(expected_frames - actual_frames))
    covered = expected_frames & actual_frames
    total = len(expected_frames)
    coverage_pct = round((len(covered) / total) * 100.0, 1) if total > 0 else 100.0

    return {
        "available": True,
        "shot_code": shot_code,
        "sequence": shot_info.get("sequence", "SQ010"),
        "cut_in": cut_in,
        "cut_out": cut_out,
        "total_cut_frames": total,
        "covered_frames": len(covered),
        "is_complete": len(missing) == 0,
        "missing_frames": missing,
        "coverage_pct": coverage_pct,
    }


