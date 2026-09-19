"""
Historical Evidence Specialist Agent module for Google ADK.
"""

from backend.agents.historical.agent import HistoricalEvidenceAgent
from backend.agents.historical.mock_history import (
    HistoricalDataStore,
    history_store,
)
from backend.agents.historical.schemas import (
    HistoricalEvidenceReport,
    HistoricalFinding,
    HistoricalPattern,
    PrecedentRecommendation,
    SimilarIncident,
)
from backend.agents.historical.similarity import (
    compute_incident_similarity,
    jaccard_similarity,
    tokenize,
)
from backend.agents.historical.tools import (
    calculate_historical_success_rate,
    get_previous_resolution,
    search_similar_incidents,
)

__all__ = [
    "HistoricalEvidenceAgent",
    "HistoricalDataStore",
    "history_store",
    "SimilarIncident",
    "HistoricalPattern",
    "PrecedentRecommendation",
    "HistoricalFinding",
    "HistoricalEvidenceReport",
    "search_similar_incidents",
    "get_previous_resolution",
    "calculate_historical_success_rate",
    "compute_incident_similarity",
    "jaccard_similarity",
    "tokenize",
]
