"""
Incident classifier and specialist agent selector.
Analyzes normalized or raw VFX events to determine incident domain and dispatch targets.
"""

from typing import Any, Optional
from backend.agents.supervisor.schemas import IncidentClassification, SpecialistName


class ClassificationReport:
    """Contains classification outcome, selected specialist names, and missing data warnings."""

    def __init__(
        self,
        classification: IncidentClassification,
        selected_specialists: list[str],
        missing_data_warnings: list[str],
        implicated_node_id: Optional[str] = None,
        implicated_job_id: Optional[str] = None,
        implicated_asset: Optional[str] = None,
    ):
        self.classification = classification
        self.selected_specialists = selected_specialists
        self.missing_data_warnings = missing_data_warnings
        self.implicated_node_id = implicated_node_id
        self.implicated_job_id = implicated_job_id
        self.implicated_asset = implicated_asset


class IncidentClassifier:
    """
    Evaluates incident payloads to classify domain and dynamically route to specialists.
    """

    @staticmethod
    def extract_entity_field(event: dict[str, Any], field_name: str) -> Optional[Any]:
        """Check top-level or nested entity dictionary."""
        if field_name in event and event[field_name] is not None:
            return event[field_name]
        entity = event.get("entity")
        if isinstance(entity, dict) and field_name in entity:
            return entity.get(field_name)
        return None

    def classify_and_route(
        self,
        event: Optional[dict[str, Any]],
        required_specialists: Optional[list[str]] = None,
    ) -> ClassificationReport:
        """
        Classifies the incident and determines the required specialist agents.
        Handles malformed events and missing data gracefully.
        """
        warnings: list[str] = []

        # 1. Guard against malformed or non-dict events
        if not isinstance(event, dict) or not event:
            warnings.append("Malformed or empty event payload provided")
            specialists = (
                required_specialists
                if required_specialists
                else [SpecialistName.RENDER_QA.value, SpecialistName.HISTORICAL_EVIDENCE.value]
            )
            return ClassificationReport(
                classification=IncidentClassification.UNKNOWN,
                selected_specialists=specialists,
                missing_data_warnings=warnings,
            )

        # 2. Extract key diagnostic fields
        raw_event_type = str(event.get("event_type", "")).upper()
        error_details = event.get("error_details") or {}
        error_code = str(event.get("error_code") or error_details.get("error_code") or "").upper()

        job_id = self.extract_entity_field(event, "job_id")
        node_id = self.extract_entity_field(event, "node_id")
        asset_name = self.extract_entity_field(event, "asset_name") or self.extract_entity_field(event, "asset_path")
        project = event.get("project") or self.extract_entity_field(event, "project")
        shot = event.get("shot") or self.extract_entity_field(event, "shot")

        # 3. Check for missing data
        if not project:
            warnings.append("Missing 'project' identification in event")
        if not shot and not job_id and not node_id:
            warnings.append("Missing primary context: neither 'shot', 'job_id', nor 'node_id' specified")
        if not raw_event_type:
            warnings.append("Missing 'event_type' field")
        if not error_code and "FAILED" in raw_event_type:
            warnings.append("Failure event missing structured 'error_code'")

        # 4. Classify Incident Type
        classification = IncidentClassification.UNKNOWN

        if any(term in raw_event_type for term in ["RENDER_JOB_FAILED", "JOB_FAILED", "RENDER_FAILED", "TASK_FAILED"]):
            classification = IncidentClassification.RENDER_FAILURE
        elif any(term in raw_event_type for term in ["NODE_UNHEALTHY", "NODE_OFFLINE", "BLADE_ERROR", "HARDWARE"]):
            classification = IncidentClassification.HARDWARE_FAULT
        elif any(term in raw_event_type for term in ["ASSET_VALIDATION_FAILED", "ASSET_MISSING", "USD_ERROR", "CORRUPT_ASSET"]):
            classification = IncidentClassification.ASSET_ANOMALY
        elif any(term in raw_event_type for term in ["FRAME_CORRUPTION_DETECTED", "FRAME_CORRUPT", "NAN_PIXELS", "BAD_PIXELS"]):
            classification = IncidentClassification.OUTPUT_CORRUPTION
        elif any(term in raw_event_type for term in ["RENDER_JOB_STARTED", "RENDER_JOB_COMPLETED"]):
            classification = IncidentClassification.LIFECYCLE_EVENT
        elif "OOM" in error_code or "MEMORY" in error_code:
            classification = IncidentClassification.RENDER_FAILURE
        elif "PCIE" in error_code or "THERMAL" in error_code:
            classification = IncidentClassification.HARDWARE_FAULT

        # 5. Determine Specialist Agents
        selected: set[str] = set()

        # If user explicitly requested specific specialists, honor them directly
        if required_specialists is not None:
            for req in required_specialists:
                selected.add(req)
        else:
            # Automatic Dynamic Selection based on incident classification
            # Always query historical pattern matching
            selected.add(SpecialistName.HISTORICAL_EVIDENCE.value)

            if classification == IncidentClassification.RENDER_FAILURE:
                selected.add(SpecialistName.RENDER_QA.value)
                # If a blade/node is implicated, also consult Hardware Diagnostic
                if node_id:
                    selected.add(SpecialistName.HARDWARE_DIAGNOSTIC.value)
                # If asset reference was mentioned in error, add Asset Validation
                if asset_name or "USD" in error_code or "TEXTURE" in error_code:
                    selected.add(SpecialistName.ASSET_VALIDATION.value)

            elif classification == IncidentClassification.HARDWARE_FAULT:
                selected.add(SpecialistName.HARDWARE_DIAGNOSTIC.value)
                # If jobs were running, check Render QA for affected tasks
                if job_id:
                    selected.add(SpecialistName.RENDER_QA.value)

            elif classification == IncidentClassification.ASSET_ANOMALY:
                selected.add(SpecialistName.ASSET_VALIDATION.value)
                if job_id or "RENDER" in raw_event_type:
                    selected.add(SpecialistName.RENDER_QA.value)

            elif classification == IncidentClassification.OUTPUT_CORRUPTION:
                selected.add(SpecialistName.RENDER_QA.value)
                selected.add(SpecialistName.ASSET_VALIDATION.value)

            elif classification == IncidentClassification.LIFECYCLE_EVENT:
                selected.add(SpecialistName.RENDER_QA.value)

            else:
                # UNKNOWN fallback: investigate broadly
                selected.add(SpecialistName.RENDER_QA.value)
                if node_id:
                    selected.add(SpecialistName.HARDWARE_DIAGNOSTIC.value)
                if asset_name:
                    selected.add(SpecialistName.ASSET_VALIDATION.value)

        # Convert to deterministic sorted list
        ordered_specialists = sorted(list(selected))

        return ClassificationReport(
            classification=classification,
            selected_specialists=ordered_specialists,
            missing_data_warnings=warnings,
            implicated_node_id=str(node_id) if node_id else None,
            implicated_job_id=str(job_id) if job_id else None,
            implicated_asset=str(asset_name) if asset_name else None,
        )
