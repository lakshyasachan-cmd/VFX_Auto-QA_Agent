"""
AI Governance Subsystem.
Implements deterministic policy evaluation, auto vs. human approval gating,
action modification with re-evaluation, and immutable audit logs.
"""

from backend.governance.policy_engine import PolicyEngine
from backend.governance.schemas import (
    ApprovalListResponse,
    ApprovalRequestDTO,
    ApprovalStatus,
    DecisionRequest,
    GovernanceDecision,
    ModifyActionRequest,
    PolicyEvaluationResult,
)
from backend.governance.service import GovernanceService, governance_service
from backend.governance.api import router as governance_router

__all__ = [
    "PolicyEngine",
    "GovernanceService",
    "governance_service",
    "governance_router",
    "ApprovalStatus",
    "GovernanceDecision",
    "PolicyEvaluationResult",
    "ApprovalRequestDTO",
    "DecisionRequest",
    "ModifyActionRequest",
    "ApprovalListResponse",
]
