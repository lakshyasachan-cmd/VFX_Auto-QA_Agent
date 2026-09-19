"""
Mock historical incident repository and resolution catalog.
Pre-seeds realistic VFX studio incident history, including:
- 17 GPU Out-Of-Memory incidents (14 successfully resolved by RETRY_ON_80GB_GPU)
- 5 Thermal throttling incidents (resolved by BLADE_QUARANTINE_AND_COOL)
- 6 Scratch disk full incidents (resolved by SCRATCH_CACHE_PURGE)
- 4 Missing asset/dependency incidents (resolved by ASSET_REPUBLISH_AND_SYNC)
"""

from typing import Any, Optional


class HistoricalDataStore:
    """In-memory historical incident and resolution archive."""

    def __init__(self) -> None:
        self.incidents: list[dict[str, Any]] = []
        self.resolutions: dict[str, dict[str, Any]] = {}
        self._seed_default_history()

    def _seed_default_history(self) -> None:
        """Seed representative historical incidents and resolutions."""

        # ── 1. 17 GPU OOM Incidents (14 resolved by RETRY_ON_80GB_GPU) ──────────
        for i in range(1, 18):
            inc_id = f"hist-oom-{i:02d}"

            if i <= 14:
                # 14 incidents successfully resolved by dispatching to high-VRAM node
                strat = "RETRY_ON_80GB_GPU"
                success = True
                summary = "Job retried on 80GB A100/H100 node; beauty pass completed successfully without memory pressure."
            elif i in (15, 16):
                # 2 incidents failed when simply retried on standard 24GB blade
                strat = "RETRY_ON_SAME_NODE"
                success = False
                summary = "Retried on same 24GB blade; failed again with identical CUDA OOM exit code 137."
            else:
                # 1 incident resolved by texture downscaling
                strat = "TEXTURE_DOWNSCALE_2K"
                success = True
                summary = "Environment textures downscaled from 8K to 2K TX; render completed within 24GB limit."

            self.incidents.append({
                "id": inc_id,
                "incident_id": inc_id,
                "title": f"Render job CUDA VRAM allocation failed on frame {1000 + i}",
                "description": f"Arnold GPU renderer ran out of memory allocating 4096MB buffer on blade node-{i:02d}",
                "event_type": "RENDER_JOB_FAILED",
                "source_system": "deadline",
                "severity": "HIGH",
                "status": "RESOLVED",
                "error_signature": "GPU_OUT_OF_MEMORY: CUDA out of memory allocation failure",
                "resolved_at": f"2026-08-{i:02d}T14:30:00Z",
                "resolution_summary": summary,
                "metadata_json": {
                    "renderer": "arnold-7.2.4",
                    "exit_code": 137,
                    "vram_used_mb": 24576,
                    "error_code": "GPU_OUT_OF_MEMORY",
                },
                "context": {
                    "renderer": "arnold-7.2.4",
                    "exit_code": 137,
                },
            })

            self.resolutions[inc_id] = {
                "incident_id": inc_id,
                "strategy": strat,
                "was_successful": success,
                "resolution_summary": summary,
                "resolved_at": f"2026-08-{i:02d}T14:30:00Z",
                "action_taken": strat,
                "nodes_involved": [f"node-{i:02d}"],
            }

        # ── 2. 5 Thermal Overheating Incidents ─────────────────────────────────
        for j in range(1, 6):
            inc_id = f"hist-thermal-{j:02d}"
            success = (j <= 4)
            strat = "BLADE_QUARANTINE_AND_COOL" if success else "RESTART_NODE_DAEMON"
            summary = "Blade quarantined from farm scheduler; fan duty cycle reset and dust filters cleaned." if success else "Daemon restart failed to alleviate junction temp above 92C."

            self.incidents.append({
                "id": inc_id,
                "incident_id": inc_id,
                "title": f"Blade render-node-{j + 10} reported critical thermal throttling",
                "description": f"GPU junction temperature hit 94C with PCIe bandwidth dropped to x1 on node-{j + 10}",
                "event_type": "NODE_UNHEALTHY",
                "source_system": "deadline",
                "severity": "CRITICAL",
                "status": "RESOLVED",
                "error_signature": "THERMAL_THROTTLING: GPU junction temperature 94C exceeded limit",
                "resolved_at": f"2026-07-{j:02d}T09:15:00Z",
                "resolution_summary": summary,
                "metadata_json": {
                    "temperature_c": 94.0,
                    "pcie_link_width": 1,
                    "throttle_status": "SW_THERMAL_SLOWDOWN",
                },
                "context": {"temperature_c": 94.0},
            })

            self.resolutions[inc_id] = {
                "incident_id": inc_id,
                "strategy": strat,
                "was_successful": success,
                "resolution_summary": summary,
                "resolved_at": f"2026-07-{j:02d}T09:15:00Z",
                "action_taken": strat,
                "nodes_involved": [f"render-node-{j + 10}"],
            }

        # ── 3. 6 Scratch Disk Full Incidents ──────────────────────────────────
        for k in range(1, 7):
            inc_id = f"hist-disk-{k:02d}"
            strat = "SCRATCH_CACHE_PURGE"
            summary = "Purged orphan .exr tile buffers and temporary caches on /scratch mount; 850GB freed."

            self.incidents.append({
                "id": inc_id,
                "incident_id": inc_id,
                "title": f"Scratch disk space exhausted on render-node-{k + 20}",
                "description": "Storage volume /scratch reached 99.9% capacity; tile buffer write failed with ENOSPC",
                "event_type": "NODE_UNHEALTHY",
                "source_system": "deadline",
                "severity": "HIGH",
                "status": "RESOLVED",
                "error_signature": "DISK_SPACE_EXHAUSTION: ENOSPC: No space left on device",
                "resolved_at": f"2026-06-{k:02d}T11:00:00Z",
                "resolution_summary": summary,
                "metadata_json": {"mount": "/scratch", "disk_utilization_pct": 99.9},
                "context": {"mount": "/scratch"},
            })

            self.resolutions[inc_id] = {
                "incident_id": inc_id,
                "strategy": strat,
                "was_successful": True,
                "resolution_summary": summary,
                "resolved_at": f"2026-06-{k:02d}T11:00:00Z",
                "action_taken": strat,
                "nodes_involved": [f"render-node-{k + 20}"],
            }

    def get_all_incidents(self) -> list[dict[str, Any]]:
        """Return all historical incident records."""
        return list(self.incidents)

    def get_incident(self, incident_id: str) -> Optional[dict[str, Any]]:
        """Return single historical incident by ID."""
        for inc in self.incidents:
            if inc.get("id") == incident_id or inc.get("incident_id") == incident_id:
                return inc
        return None

    def get_resolution(self, incident_id: str) -> Optional[dict[str, Any]]:
        """Return previous resolution details for an incident."""
        return self.resolutions.get(incident_id)

    def add_incident(self, incident_dict: dict[str, Any], resolution_dict: Optional[dict[str, Any]] = None) -> None:
        """Add an incident record to the archive."""
        inc_id = incident_dict.get("id") or incident_dict.get("incident_id") or "inc-custom"
        self.incidents.append(incident_dict)
        if resolution_dict:
            self.resolutions[inc_id] = resolution_dict

    def reset_defaults(self) -> None:
        """Reset archive to default seeded state."""
        self.incidents.clear()
        self.resolutions.clear()
        self._seed_default_history()


# Global historical store singleton
history_store = HistoricalDataStore()
