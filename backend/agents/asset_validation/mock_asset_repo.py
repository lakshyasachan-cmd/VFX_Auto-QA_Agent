"""
Simulated VFX Asset Repository and mock asset dependency graph.
Models complex production asset graphs:
- USD scenes, sublayers, and references
- Alembic (.abc) point and transform caches
- OpenVDB (.vdb) volumetric simulations and grid channels
- EXR/TX texture maps and UDIM sequences
- Broken references, missing files, corrupt archives, and version mismatches
- Cyclic composition loop containment
"""

from typing import Optional
from backend.agents.asset_validation.schemas import (
    AssetNode,
    AssetType,
)


class AssetRepositoryStore:
    """In-memory asset repository simulating a studio storage volume (e.g., /shows/)."""

    def __init__(self) -> None:
        self.assets: dict[str, AssetNode] = {}
        self.path_lookup: dict[str, str] = {}
        self._seed_default_assets()

    def _seed_default_assets(self) -> None:
        """Seed representative production asset hierarchies."""

        # ── 1. Healthy Shot Graph (asset_shot_clean) ──────────────────────────
        self._add_node(
            AssetNode(
                asset_id="asset_shot_clean",
                file_path="/shows/PROJ/shots/SH020/shot_clean.usda",
                asset_type=AssetType.USD,
                version="v001",
                expected_version="v001",
                file_size_bytes=45000,
                dependencies=["asset_clean_hero", "asset_clean_env", "asset_clean_fx"],
                metadata={"shot": "SH020", "fps": 24.0},
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_clean_hero",
                file_path="/shows/PROJ/assets/char/hero/hero.usd",
                asset_type=AssetType.USD,
                version="v003",
                expected_version="v003",
                file_size_bytes=12000,
                dependencies=["asset_clean_hero_geom", "asset_clean_hero_anim", "asset_clean_hero_tex_1001"],
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_clean_hero_geom",
                file_path="/shows/PROJ/assets/char/hero/hero_geom_v003.usdc",
                asset_type=AssetType.USD,
                version="v003",
                expected_version="v003",
                file_size_bytes=24000000,
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_clean_hero_anim",
                file_path="/shows/PROJ/caches/char/hero/hero_anim_v003.abc",
                asset_type=AssetType.ALEMBIC,
                version="v003",
                expected_version="v003",
                file_size_bytes=142000000,
                metadata={"format": "Ogawa", "frame_range": [1001, 1050]},
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_clean_hero_tex_1001",
                file_path="/shows/PROJ/textures/hero/diffuse.1001.tx",
                asset_type=AssetType.EXR_TEXTURE,
                version="v001",
                expected_version="v001",
                file_size_bytes=35000000,
                metadata={"resolution": "4096x4096", "colorspace": "ACEScg", "udim": 1001},
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_clean_env",
                file_path="/shows/PROJ/assets/env/city/city.usd",
                asset_type=AssetType.USD,
                version="v004",
                expected_version="v004",
                file_size_bytes=89000000,
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_clean_fx",
                file_path="/shows/PROJ/caches/fx/smoke/smoke_v002.vdb",
                asset_type=AssetType.OPENVDB,
                version="v002",
                expected_version="v002",
                file_size_bytes=450000000,
                metadata={"grids": ["density", "temperature", "velocity"], "frame_range": [1001, 1050]},
            )
        )

        # ── 2. Broken USD Reference Graph (asset_shot_broken_usd_ref) ─────────
        self._add_node(
            AssetNode(
                asset_id="asset_shot_broken_usd_ref",
                file_path="/shows/PROJ/shots/SH010/shot_broken_usd.usda",
                asset_type=AssetType.USD,
                version="v001",
                expected_version="v001",
                file_size_bytes=32000,
                dependencies=["asset_knight_stage"],
                metadata={"shot": "SH010"},
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_knight_stage",
                file_path="/shows/PROJ/assets/char/knight/knight.usd",
                asset_type=AssetType.USD,
                version="v002",
                expected_version="v002",
                file_size_bytes=15000,
                dependencies=["asset_missing_sublayer_sword"],
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_missing_sublayer_sword",
                file_path="/shows/PROJ/assets/prop/sword/sword_v002.usdc",
                asset_type=AssetType.USD,
                version="v002",
                expected_version="v002",
                file_size_bytes=0,
                exists_on_disk=False,  # Broken file reference
                corruption_reason="File does not exist on storage mount (ENOENT)",
            )
        )

        # ── 3. Missing UDIM Texture Sequence Graph (asset_shot_missing_udim) ───
        self._add_node(
            AssetNode(
                asset_id="asset_shot_missing_udim",
                file_path="/shows/PROJ/shots/SH015/shot_missing_udim.usda",
                asset_type=AssetType.USD,
                version="v001",
                expected_version="v001",
                dependencies=["asset_car_model"],
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_car_model",
                file_path="/shows/PROJ/assets/props/car/car.usd",
                asset_type=AssetType.USD,
                version="v002",
                dependencies=["asset_car_tex_1001", "asset_car_tex_1002"],
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_car_tex_1001",
                file_path="/shows/PROJ/textures/car/diffuse.1001.tx",
                asset_type=AssetType.EXR_TEXTURE,
                version="v001",
                exists_on_disk=True,
                metadata={"udim": 1001},
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_car_tex_1002",
                file_path="/shows/PROJ/textures/car/diffuse.1002.tx",
                asset_type=AssetType.EXR_TEXTURE,
                version="v001",
                exists_on_disk=False,  # Missing UDIM tile
                file_size_bytes=0,
                corruption_reason="UDIM tile 1002 missing from published texture sequence",
                metadata={"udim": 1002},
            )
        )

        # ── 4. Corrupted Alembic Cache Graph (asset_shot_corrupted_alembic) ────
        self._add_node(
            AssetNode(
                asset_id="asset_shot_corrupted_alembic",
                file_path="/shows/PROJ/shots/SH030/shot_corrupted_abc.usda",
                asset_type=AssetType.USD,
                version="v001",
                dependencies=["asset_dragon_anim_corrupt"],
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_dragon_anim_corrupt",
                file_path="/shows/PROJ/caches/creature/dragon/dragon_anim_v001.abc",
                asset_type=AssetType.ALEMBIC,
                version="v001",
                file_size_bytes=16,  # Truncated header
                exists_on_disk=True,
                is_corrupted=True,
                corruption_reason="Corrupted Ogawa header: truncated archive (16 bytes, expected >100MB)",
                metadata={"format": "Ogawa"},
            )
        )

        # ── 5. Missing OpenVDB Grids & Frames (asset_shot_missing_vdb) ─────────
        self._add_node(
            AssetNode(
                asset_id="asset_shot_missing_vdb",
                file_path="/shows/PROJ/shots/SH040/shot_missing_vdb.usda",
                asset_type=AssetType.USD,
                version="v001",
                dependencies=["asset_explosion_vdb"],
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_explosion_vdb",
                file_path="/shows/PROJ/caches/fx/explosion/fire_v002.vdb",
                asset_type=AssetType.OPENVDB,
                version="v002",
                file_size_bytes=84000000,
                exists_on_disk=True,
                is_corrupted=True,
                corruption_reason="Missing required volumetric grid 'density' (only 'flame' present); frame 1042 missing",
                metadata={
                    "available_grids": ["flame"],
                    "required_grids": ["density", "flame"],
                    "missing_frames": [1042],
                    "frame_range": [1001, 1050],
                },
            )
        )

        # ── 6. Version Mismatch Graph (asset_shot_version_mismatch) ────────────
        self._add_node(
            AssetNode(
                asset_id="asset_shot_version_mismatch",
                file_path="/shows/PROJ/shots/SH050/shot_version_mismatch.usda",
                asset_type=AssetType.USD,
                version="v001",
                dependencies=["asset_bridge_deprecated"],
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_bridge_deprecated",
                file_path="/shows/PROJ/assets/env/bridge/bridge.usd",
                asset_type=AssetType.USD,
                version="v001",
                expected_version="v004",  # Pipeline published v004
                exists_on_disk=True,
                metadata={
                    "is_incompatible": True,
                    "breaking_change": "v001 uses deprecated UsdGeomBasisCurves schema incompatible with current Arnold renderer",
                },
            )
        )

        # ── 7. Cyclic Reference Graph (asset_shot_cyclic) ──────────────────────
        self._add_node(
            AssetNode(
                asset_id="asset_shot_cyclic",
                file_path="/shows/PROJ/shots/SH060/shot_cyclic.usda",
                asset_type=AssetType.USD,
                version="v001",
                dependencies=["asset_loop_a"],
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_loop_a",
                file_path="/shows/PROJ/assets/loop/stage_a.usd",
                asset_type=AssetType.USD,
                version="v001",
                dependencies=["asset_loop_b"],
            )
        )
        self._add_node(
            AssetNode(
                asset_id="asset_loop_b",
                file_path="/shows/PROJ/assets/loop/stage_b.usd",
                asset_type=AssetType.USD,
                version="v001",
                dependencies=["asset_loop_a"],  # Direct cycle
            )
        )

    def _add_node(self, node: AssetNode) -> None:
        self.assets[node.asset_id] = node
        self.path_lookup[node.file_path] = node.asset_id

    def get_asset(self, asset_id: str) -> Optional[AssetNode]:
        """Fetch asset node by unique asset ID."""
        return self.assets.get(asset_id)

    def get_asset_by_path(self, file_path: str) -> Optional[AssetNode]:
        """Fetch asset node by storage filepath."""
        asset_id = self.path_lookup.get(file_path)
        if asset_id:
            return self.assets.get(asset_id)
        return None

    def register_asset(self, node: AssetNode) -> None:
        """Register or overwrite an asset node in the repository."""
        self._add_node(node)

    def reset_defaults(self) -> None:
        """Reset repository to default test fixtures."""
        self.assets.clear()
        self.path_lookup.clear()
        self._seed_default_assets()


# Global asset repository singleton
asset_repo = AssetRepositoryStore()
