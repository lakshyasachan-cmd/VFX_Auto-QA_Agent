"""
VFX Asset Validation Specialist Agent.
Investigates USD stage dependencies, Alembic caches, OpenVDB volumes, and EXR textures.
Detects missing files, broken references, corrupted archives, version discrepancies, and cyclic references.

STRICT INVARIANTS:
1. The agent must NEVER modify assets (strictly read-only inspection).
2. Never claim an asset exists or invent evidence if not supplied in the catalog.
3. Clearly distinguish OBSERVED, INFERRED, and UNKNOWN epistemic facts.
4. DOES NOT execute remediation actions.
"""

from typing import Any, Optional
from backend.agents.asset_validation.mock_asset_repo import (
    AssetRepositoryStore,
    asset_repo,
)
from backend.agents.asset_validation.schemas import (
    AssetValidationFinding,
    AssetValidationReport,
)
from backend.agents.asset_validation.tools import (
    check_dependencies,
    detect_missing_assets,
    detect_version_mismatch,
    validate_asset,
    validate_file_integrity,
)
from backend.agents.supervisor.schemas import (
    AgentFindingDTO,
    EvidenceItemDTO,
    SpecialistName,
    SpecialistReport,
)
from backend.agents.supervisor.specialist_interface import BaseSpecialistAgent


class AssetValidationAgent(BaseSpecialistAgent):
    """
    Asset Validation Specialist Agent implemented for Google ADK.
    Deeply inspects scene graphs, composition arcs, geometry caches, volume grids,
    and texture maps to pinpoint asset-level failures in the VFX pipeline.
    """

    name: str = SpecialistName.ASSET_VALIDATION.value
    description: str = (
        "Specialist agent that analyzes USD composition arcs, sublayer references, "
        "Alembic point caches, OpenVDB volumetric grids, UDIM textures, and version mismatches."
    )

    # Injected repository store (defaults to studio singleton asset_repo)
    store: AssetRepositoryStore = None  # type: ignore

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.store is None:
            self.store = asset_repo

    def analyze_asset(
        self,
        asset_id: str,
        context: Optional[dict[str, Any]] = None,
    ) -> AssetValidationReport:
        """
        Core diagnostic workflow:
        1. validate_asset (check root asset integrity)
        2. check_dependencies (traverse transitive dependency tree and detect cycles)
        3. detect_missing_assets (identify broken USD references, missing textures/caches)
        4. detect_version_mismatch (compare against approved publish versions)
        5. validate_file_integrity (inspect corrupted headers/truncation)
        6. Epistemic synthesis (OBSERVED vs INFERRED vs UNKNOWN)
        """
        _ = context
        findings: list[AssetValidationFinding] = []
        all_missing_ids: list[str] = []
        all_corrupt_ids: list[str] = []
        all_mismatch_ids: list[str] = []

        # 1. Validate root asset
        root_val = validate_asset(asset_id, store=self.store)
        if not root_val.get("available"):
            # Missing root asset -> strictly UNKNOWN, zero invented evidence
            reason = root_val.get("reason", f"Asset '{asset_id}' not found in catalog")
            f_missing_root = AssetValidationFinding(
                agent="asset_validation",
                finding_type="ASSET_NOT_FOUND",
                severity="HIGH",
                confidence=0.0,
                evidence=[],
                asset_ids=[asset_id],
                dependency_chain=[asset_id],
                observed=[],
                inferred=[],
                unknown=[reason, f"No catalog entry exists for asset '{asset_id}'"],
                details={"asset_id": asset_id, "reason": reason},
            )
            return AssetValidationReport(
                agent="asset_validation",
                root_asset_id=asset_id,
                is_valid=False,
                total_assets_inspected=0,
                missing_asset_ids=[asset_id],
                corrupt_asset_ids=[],
                version_mismatches=[],
                dependency_chain=[asset_id],
                findings=[f_missing_root],
                overall_confidence=0.0,
                summary=f"Validation aborted: Asset '{asset_id}' does not exist in repository.",
            )

        # 2. Dependency traversal
        dep_res = check_dependencies(asset_id, depth=10, store=self.store)
        dep_chain = dep_res.get("dependency_chain", [asset_id])
        total_inspected = len(dep_res.get("visited_asset_ids", [asset_id]))

        # Check for cycles
        cycles = dep_res.get("cycles_detected", [])
        if cycles:
            for cycle in cycles:
                cycle_str = " -> ".join(cycle)
                f_cycle = AssetValidationFinding(
                    agent="asset_validation",
                    finding_type="CYCLIC_DEPENDENCY_DETECTED",
                    severity="CRITICAL",
                    confidence=0.99,
                    evidence=[f"Circular composition loop detected in USD stage: {cycle_str}"],
                    asset_ids=cycle,
                    dependency_chain=cycle,
                    observed=[f"Composition reference loop: {cycle_str}"],
                    inferred=["Renderer will enter infinite recursion or fail with stack overflow on stage load"],
                    unknown=["Whether cycle was introduced by manual artist edit or broken script export"],
                    details={"cycle": cycle},
                )
                findings.append(f_cycle)

        # 3. Detect missing dependencies
        missing_res = detect_missing_assets(asset_id, store=self.store)
        missing_list = missing_res.get("missing_assets", [])

        # Group missing items by asset_id to produce unified finding per problematic asset
        missing_by_asset: dict[str, list[dict[str, Any]]] = {}
        for m in missing_list:
            m_id = m.get("asset_id", "unknown_asset")
            missing_by_asset.setdefault(m_id, []).append(m)

        for m_id, items in missing_by_asset.items():
            all_missing_ids.append(m_id)
            first = items[0]
            m_path = first.get("file_path") or "unspecified_path"
            ref_by = first.get("referenced_by", asset_id)
            reasons = [it.get("reason", "File missing") for it in items]
            combined_reason = "; ".join(reasons)

            # Determine specific finding type
            if any("UDIM" in r or ".tx" in m_path or "texture" in r.lower() for r in reasons):
                ftype = "MISSING_TEXTURE_MAP"
                sev = "HIGH"
            elif any("VDB" in r or "grid" in r.lower() or "frame" in r.lower() for r in reasons):
                ftype = "MISSING_CACHE_FRAME_OR_GRID"
                sev = "HIGH"
            elif ".usdc" in m_path or ".usd" in m_path or any("sublayer" in r.lower() for r in reasons):
                ftype = "BROKEN_USD_REFERENCE"
                sev = "CRITICAL"
            else:
                ftype = "MISSING_DEPENDENCY"
                sev = "HIGH"

            evidence_lines = [
                f"Missing asset dependency: '{m_id}' ({m_path})",
                f"Referenced by: '{ref_by}'",
            ]
            for r in reasons:
                evidence_lines.append(f"Reason: {r}")

            observed_lines = [
                f"Referenced path '{m_path}' does not resolve to an accessible file or grid channel on disk",
                f"Inspection details: {combined_reason}",
                f"Referencing stage: '{ref_by}'",
            ]

            f_missing = AssetValidationFinding(
                agent="asset_validation",
                finding_type=ftype,
                severity=sev,
                confidence=0.98,
                evidence=evidence_lines,
                asset_ids=[ref_by, m_id],
                dependency_chain=dep_chain,
                observed=observed_lines,
                inferred=[
                    f"Downstream render delegate will fail when attempting to resolve '{m_id}'",
                    "Asset was published with uncopied local disk dependencies or publish script aborted",
                ],
                unknown=[
                    "Exact artist workstation path where the uncopied asset originally resided",
                ],
                details={"asset_id": m_id, "items": items, "reasons": reasons},
            )
            findings.append(f_missing)

        # 4. Detect corrupted assets
        corrupt_list = dep_res.get("corrupt_dependencies", [])
        for c in corrupt_list:
            c_id = c.get("asset_id", "unknown_asset")
            c_path = c.get("file_path") or ""
            c_reason = c.get("reason", "Corrupted file")
            all_corrupt_ids.append(c_id)

            # Run detailed file integrity check
            integ = validate_file_integrity(c_path, store=self.store)

            f_corrupt = AssetValidationFinding(
                agent="asset_validation",
                finding_type="CORRUPTED_ASSET_DATA",
                severity="CRITICAL",
                confidence=0.97,
                evidence=[
                    f"Corrupted asset detected: '{c_id}' ({c_path})",
                    f"Reason: {c_reason}",
                    f"File size on disk: {integ.get('file_size_bytes', 0)} bytes (Header valid: {integ.get('header_valid')})",
                ],
                asset_ids=[c_id],
                dependency_chain=dep_chain,
                observed=[
                    f"Archive header for '{c_path}' failed integrity validation: {integ.get('error_message')}",
                    f"Physical file size: {integ.get('file_size_bytes', 0)} bytes",
                ],
                inferred=[
                    "Render engine will segfault or raise unrecoverable read exception when loading cache",
                    "File transfer was terminated prematurely during publish sync",
                ],
                unknown=[
                    "Whether source DCC session crashed during original geometry cache export",
                ],
                details={"asset_id": c_id, "integrity": integ},
            )
            findings.append(f_corrupt)

        # 5. Detect version mismatches
        version_res = detect_version_mismatch(asset_id, store=self.store)
        mismatch_list = version_res.get("mismatches", [])
        for vm in mismatch_list:
            vm_id = vm.get("asset_id", "unknown_asset")
            ref_ver = vm.get("referenced_version")
            exp_ver = vm.get("expected_version")
            is_incomp = vm.get("is_incompatible", False)
            all_mismatch_ids.append(vm_id)

            f_type = "INCOMPATIBLE_ASSET_VERSION" if is_incomp else "ASSET_VERSION_MISMATCH"
            sev = "CRITICAL" if is_incomp else "MEDIUM"

            f_ver = AssetValidationFinding(
                agent="asset_validation",
                finding_type=f_type,
                severity=sev,
                confidence=0.95,
                evidence=[
                    f"Version discrepancy in asset '{vm_id}': references '{ref_ver}', expected published '{exp_ver}'",
                    vm.get("details", ""),
                ],
                asset_ids=[vm_id],
                dependency_chain=dep_chain,
                observed=[
                    f"Asset '{vm_id}' is pinned to version '{ref_ver}' while active pipeline version is '{exp_ver}'",
                    f"Breaking incompatibility flag: {is_incomp}",
                ],
                inferred=[
                    "Deprecated schema or modified attribute types in older asset version cause rendering errors",
                    "Shot stage was not updated after approved department asset publish",
                ],
                unknown=[
                    "Whether artist deliberately pinned older version for aesthetic consistency",
                ],
                details=vm,
            )
            findings.append(f_ver)

        # 6. Healthy Asset Graph
        is_valid = len(findings) == 0
        if is_valid:
            f_clean = AssetValidationFinding(
                agent="asset_validation",
                finding_type="ASSET_GRAPH_VALID",
                severity="INFO",
                confidence=0.96,
                evidence=[
                    f"Asset '{asset_id}' and all {total_inspected} dependencies verified intact",
                    "All USD references, Alembic geometry caches, VDB volumes, and UDIM textures present and uncorrupted",
                    "All asset versions align with pipeline publication standards",
                ],
                asset_ids=[asset_id],
                dependency_chain=dep_chain,
                observed=[
                    f"Inspected {total_inspected} asset node(s) across stage graph",
                    "0 missing files, 0 corrupted headers, 0 version discrepancies, 0 dependency cycles",
                ],
                inferred=[
                    "Scene assets are structurally sound and ready for farm dispatch",
                ],
                unknown=[
                    "Dynamic runtime shader procedural allocations during render",
                ],
                details={"total_dependencies": total_inspected},
            )
            findings.append(f_clean)

        overall_conf = max((f.confidence for f in findings), default=0.95)
        summary = (
            f"Asset validation for '{asset_id}': Inspected {total_inspected} asset(s). "
            f"Found {len(findings)} finding(s) (Missing: {len(all_missing_ids)}, Corrupt: {len(all_corrupt_ids)}, "
            f"Mismatches: {len(all_mismatch_ids)})."
        )

        return AssetValidationReport(
            agent="asset_validation",
            root_asset_id=asset_id,
            is_valid=is_valid,
            total_assets_inspected=total_inspected,
            missing_asset_ids=all_missing_ids,
            corrupt_asset_ids=all_corrupt_ids,
            version_mismatches=all_mismatch_ids,
            dependency_chain=dep_chain,
            findings=findings,
            overall_confidence=overall_conf,
            summary=summary,
        )

    async def investigate(self, incident_id: str, event: dict[str, Any]) -> SpecialistReport:
        """
        Implementation of the Google ADK BaseSpecialistAgent contract.
        Returns a SpecialistReport compatible with the Supervisor Agent.
        STRICT RULE: The agent only inspects and reports; NEVER modifies assets.
        """
        # Extract target asset identifier from incident event
        asset_id = (
            event.get("asset_id")
            or event.get("entity", {}).get("asset_name")
            or event.get("entity", {}).get("asset_id")
            or event.get("entity", {}).get("entity_id")
            or "asset_shot_clean"
        )

        report = self.analyze_asset(str(asset_id), context=event)

        # Convert findings to AgentFindingDTO
        dto_findings: list[AgentFindingDTO] = []
        for f in report.findings:
            dto_findings.append(
                AgentFindingDTO(
                    agent_name=self.name,
                    finding_type=f.finding_type,
                    category="asset",
                    severity=f.severity,
                    confidence=f.confidence,
                    title=f.finding_type.replace("_", " ").title(),
                    description=f"Observed: {'; '.join(f.observed)}. Inferred: {'; '.join(f.inferred)}",
                    evidence_ids=[],
                    details={
                        "evidence": f.evidence,
                        "asset_ids": f.asset_ids,
                        "dependency_chain": f.dependency_chain,
                        "observed": f.observed,
                        "inferred": f.inferred,
                        "unknown": f.unknown,
                        "details": f.details,
                    },
                )
            )

        # Convert evidence to EvidenceItemDTO
        dto_evidence: list[EvidenceItemDTO] = []
        for idx, f in enumerate(report.findings):
            for ev_idx, ev_line in enumerate(f.evidence):
                dto_evidence.append(
                    EvidenceItemDTO(
                        evidence_type="USD_STAGE",
                        source=self.name,
                        title=f"Asset Validation Evidence #{idx+1}.{ev_idx+1} ({f.finding_type})",
                        content=ev_line,
                        structured_data={
                            "asset_id": report.root_asset_id,
                            "affected_assets": f.asset_ids,
                            "dependency_chain": f.dependency_chain,
                            "evidence": ev_line,
                        },
                    )
                )

        hypotheses = [
            {
                "agent_name": self.name,
                "hypothesis": f"{f.finding_type}: {'; '.join(f.inferred)}",
                "confidence": f.confidence,
                "claim_type": "asset",
            }
            for f in report.findings
        ]

        return SpecialistReport(
            agent_name=self.name,
            status="SUCCESS",
            findings=dto_findings,
            evidence=dto_evidence,
            hypotheses=hypotheses,
        )
