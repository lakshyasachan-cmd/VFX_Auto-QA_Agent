"""
Historical incident inspection tools for the VFX platform.
Functions:
1. search_similar_incidents(current_incident, limit, min_similarity)
2. get_previous_resolution(incident_id)
3. calculate_historical_success_rate(strategy, similar_incident_ids)

Supports both PostgreSQL / SQLAlchemy live sessions and standalone in-memory history_store.
"""

import logging
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("vfx.agents.historical.tools")

from backend.agents.historical.mock_history import (
    HistoricalDataStore,
    history_store,
)
from backend.agents.historical.schemas import SimilarIncident
from backend.agents.historical.similarity import compute_incident_similarity
from backend.database.models.incident import Incident
from backend.database.models.remediation import RemediationPlan


def get_previous_resolution(
    incident_id: str,
    session: Optional[Session] = None,
    store: Optional[HistoricalDataStore] = None,
) -> Optional[dict[str, Any]]:
    """
    Retrieve prior resolution strategy and outcome for a given historical incident ID.
    Queries live PostgreSQL database if session provided; otherwise queries history_store.
    """
    # 1. Check live database if session provided
    if session is not None:
        try:
            stmt = (
                select(Incident)
                .where(Incident.id == incident_id)
            )
            inc_record = session.scalar(stmt)
            if inc_record:
                # Check for linked remediation plan
                plan_stmt = (
                    select(RemediationPlan)
                    .where(RemediationPlan.incident_id == incident_id)
                    .order_by(RemediationPlan.created_at.desc())
                )
                plan = session.scalar(plan_stmt)
                strat = plan.strategy if plan else (inc_record.resolution_summary or "UNKNOWN_STRATEGY")
                success = (inc_record.status == "RESOLVED")
                return {
                    "incident_id": inc_record.id,
                    "strategy": strat,
                    "was_successful": success,
                    "resolution_summary": inc_record.resolution_summary or "",
                    "resolved_at": inc_record.resolved_at.isoformat() if inc_record.resolved_at else None,
                    "action_taken": strat,
                }
        except Exception as exc:
            logger.warning("Error querying resolution for incident '%s' from DB: %s", incident_id, exc)


    # 2. Check in-memory store
    s = store or history_store
    return s.get_resolution(incident_id)


def search_similar_incidents(
    current_incident: dict[str, Any],
    limit: int = 20,
    min_similarity: float = 0.5,
    session: Optional[Session] = None,
    store: Optional[HistoricalDataStore] = None,
) -> list[SimilarIncident]:
    """
    Search historical incident repository for incidents similar to the current incident.
    Computes similarity across event types, error signatures, tokens, and renderer context.
    Returns ranked list of SimilarIncident records exceeding min_similarity.
    """
    candidates: list[dict[str, Any]] = []

    # 1. Fetch from PostgreSQL database if session provided
    if session is not None:
        try:
            stmt = select(Incident).order_by(Incident.created_at.desc()).limit(100)
            db_records = session.scalars(stmt).all()
            for rec in db_records:
                candidates.append({
                    "id": rec.id,
                    "incident_id": rec.id,
                    "title": rec.title,
                    "description": rec.description,
                    "event_type": rec.event_type,
                    "source_system": rec.source_system,
                    "status": rec.status,
                    "error_signature": rec.error_signature,
                    "resolved_at": rec.resolved_at.isoformat() if rec.resolved_at else None,
                    "resolution_summary": rec.resolution_summary,
                    "metadata_json": rec.metadata_json or {},
                })
        except Exception as exc:
            logger.warning("Failed querying PostgreSQL historical incidents: %s. Falling back to history_store.", exc)


    # 2. Fetch from history_store (or fallback if candidates empty)
    if not candidates:
        s = store or history_store
        candidates = s.get_all_incidents()

    matches: list[SimilarIncident] = []

    for cand in candidates:
        # Don't match incident against itself
        c_id = cand.get("id") or cand.get("incident_id")
        if c_id and c_id == current_incident.get("incident_id"):
            continue

        score = compute_incident_similarity(current_incident, cand)
        if score >= min_similarity:
            # Fetch resolution info
            res_info = get_previous_resolution(c_id, session=session, store=store)
            strat = res_info.get("strategy") if res_info else cand.get("resolution_summary")
            success = res_info.get("was_successful", True) if res_info else (cand.get("status") == "RESOLVED")

            match_item = SimilarIncident(
                incident_id=str(c_id),
                title=cand.get("title", "Untitled Incident"),
                event_type=cand.get("event_type", "UNKNOWN"),
                error_signature=cand.get("error_signature"),
                similarity_score=score,
                status=cand.get("status", "RESOLVED"),
                resolved_at=cand.get("resolved_at"),
                resolution_summary=res_info.get("resolution_summary") if res_info else cand.get("resolution_summary"),
                remediation_strategy=strat,
                was_successful=success,
                context=cand.get("context", {}),
            )
            matches.append(match_item)

    # Sort descending by similarity score
    matches.sort(key=lambda x: x.similarity_score, reverse=True)
    return matches[:limit]


def calculate_historical_success_rate(
    strategy: str,
    similar_incident_ids: list[str],
    session: Optional[Session] = None,
    store: Optional[HistoricalDataStore] = None,
) -> dict[str, Any]:
    """
    Calculate the success/failure rate of a specific remediation strategy
    across a subset of similar historical incident IDs.
    """
    sample_size = 0
    success_count = 0
    failure_count = 0

    for inc_id in similar_incident_ids:
        res = get_previous_resolution(inc_id, session=session, store=store)
        if res and res.get("strategy") == strategy:
            sample_size += 1
            if res.get("was_successful", False):
                success_count += 1
            else:
                failure_count += 1

    success_rate = (success_count / sample_size) if sample_size > 0 else 0.0

    return {
        "strategy": strategy,
        "sample_size": sample_size,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_rate, 3),
    }
