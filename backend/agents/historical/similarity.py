"""
Similarity scoring mechanism for VFX incidents.
Computes multi-attribute weighted token & metadata similarity without external vector database dependencies.
Designed for PostgreSQL attribute queries and in-memory scoring.
"""

import re
from typing import Any, Optional

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "with", "by", "of", "from",
    "is", "was", "are", "were", "and", "or", "not", "be", "has", "have", "had",
    "it", "its", "as", "error", "failed", "failure",
}


def tokenize(text: Optional[str]) -> set[str]:
    """Tokenize error text into normalized words, excluding common stop words."""
    if not text:
        return set()
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return {t for t in tokens if t not in STOP_WORDS and len(t) > 1}


def jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Calculate standard Jaccard token similarity."""
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def compute_incident_similarity(
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> float:
    """
    Computes a composite similarity score between 0.0 and 1.0:
    - Error Domain & Token Overlap (Weight: 0.45)
    - Event Type Match (Weight: 0.30)
    - Source System Alignment (Weight: 0.15)
    - Contextual Entity & Exit Code Match (Weight: 0.10)

    Enforces that incidents with distinct/unrelated error failure domains
    do NOT match even if they share an event type.
    """
    # 1. Error text extraction
    curr_err = (
        str(current.get("error_signature") or "") + " " +
        str(current.get("title") or "") + " " +
        str(current.get("error_details", {}).get("message") or "") + " " +
        str(current.get("error_details", {}).get("error_code") or "")
    )
    cand_err = (
        str(candidate.get("error_signature") or "") + " " +
        str(candidate.get("title") or "") + " " +
        str(candidate.get("description") or "") + " " +
        str(candidate.get("metadata_json", {}).get("error_message") or "")
    )

    tokens_curr = tokenize(curr_err)
    tokens_cand = tokenize(cand_err)
    jaccard = jaccard_similarity(tokens_curr, tokens_cand)

    # Specific failure mode signature definitions
    memory_terms = {"oom", "cuda_oom", "out_of_memory", "vram", "allocation"}
    thermal_terms = {"thermal", "overheating", "throttling", "temperature", "slowdown"}
    disk_terms = {"enospc", "disk", "scratch", "no_space", "space"}
    driver_terms = {"xid", "driver", "unresponsive", "device_handle"}
    asset_terms = {"usd", "sublayer", "alembic", "udim", "texture"}

    domain_match = False
    for domain in [memory_terms, thermal_terms, disk_terms, driver_terms, asset_terms]:
        if (tokens_curr & domain) and (tokens_cand & domain):
            domain_match = True
            break

    if domain_match:
        token_score = max(jaccard, 0.72 + 0.28 * jaccard)
    else:
        token_score = jaccard

    # Gating rule: If error tokens have negligible overlap and no failure domain match,
    # the incident cannot be historically similar (prevents cross-domain pollution)
    if token_score < 0.15 and not domain_match:
        return round(0.15 * token_score, 3)

    # 2. Event Type Match (Weight: 0.30)
    curr_type = str(current.get("event_type", "")).upper()
    cand_type = str(candidate.get("event_type", "")).upper()
    if curr_type == cand_type:
        event_score = 1.0
    elif {curr_type, cand_type} <= {"RENDER_JOB_FAILED", "FRAME_CORRUPTION_DETECTED"}:
        event_score = 0.5
    else:
        event_score = 0.2

    # 3. Source System Alignment (Weight: 0.15)
    curr_src = str(current.get("source") or current.get("source_system", "")).lower()
    cand_src = str(candidate.get("source_system") or candidate.get("source", "")).lower()
    source_score = 1.0 if (curr_src and curr_src == cand_src) else 0.3

    # 4. Contextual Match: Exit Code (Weight: 0.10)
    curr_exit = current.get("error_details", {}).get("exit_code") or current.get("metadata", {}).get("exit_code")
    cand_exit = candidate.get("metadata_json", {}).get("exit_code") or candidate.get("context", {}).get("exit_code")

    context_score = 0.5
    if curr_exit is not None and cand_exit is not None:
        context_score = 1.0 if curr_exit == cand_exit else 0.2

    final_score = (
        0.45 * token_score +
        0.30 * event_score +
        0.15 * source_score +
        0.10 * context_score
    )

    return round(min(max(final_score, 0.0), 1.0), 3)
