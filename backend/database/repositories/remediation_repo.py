"""
Repositories for RemediationPlans, ApprovalRequests, and Actions.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.database.models.remediation import (
    Action,
    ApprovalRequest,
    RemediationPlan,
)
from backend.database.repositories.base import BaseRepository


class RemediationPlanRepository(BaseRepository[RemediationPlan]):
    def __init__(self, session: Session):
        super().__init__(RemediationPlan, session)

    def list_by_incident(self, incident_id: str) -> list[RemediationPlan]:
        stmt = (
            select(RemediationPlan)
            .where(RemediationPlan.incident_id == incident_id)
            .options(
                selectinload(RemediationPlan.approval_requests),
                selectinload(RemediationPlan.actions),
            )
            .order_by(RemediationPlan.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def get_with_actions(self, plan_id: str) -> Optional[RemediationPlan]:
        stmt = (
            select(RemediationPlan)
            .where(RemediationPlan.id == plan_id)
            .options(
                selectinload(RemediationPlan.approval_requests),
                selectinload(RemediationPlan.actions),
            )
        )
        return self.session.scalars(stmt).first()


class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    def __init__(self, session: Session):
        super().__init__(ApprovalRequest, session)

    def list_pending(self) -> list[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "PENDING")
            .order_by(ApprovalRequest.requested_at)
        )
        return list(self.session.scalars(stmt).all())

    def decide(
        self,
        approval_id: str,
        decision: str,  # APPROVED or REJECTED
        decided_by: str,
        reason: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        req = self.get_by_id(approval_id)
        if req:
            req.status = decision.upper()
            req.decided_at = datetime.now(timezone.utc)
            req.decided_by = decided_by
            req.decision_reason = reason
            self.session.commit()
            self.session.refresh(req)
        return req


class ActionRepository(BaseRepository[Action]):
    def __init__(self, session: Session):
        super().__init__(Action, session)

    def list_by_plan(self, plan_id: str) -> list[Action]:
        stmt = (
            select(Action)
            .where(Action.plan_id == plan_id)
            .order_by(Action.execution_order)
        )
        return list(self.session.scalars(stmt).all())

    def update_execution(
        self,
        action_id: str,
        status: str,  # COMPLETED or FAILED
        result_payload: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Action]:
        act = self.get_by_id(action_id)
        if act:
            act.status = status
            act.executed_at = datetime.now(timezone.utc)
            if result_payload:
                act.result_payload = result_payload
            if error_message:
                act.error_message = error_message
            self.session.commit()
            self.session.refresh(act)
        return act
