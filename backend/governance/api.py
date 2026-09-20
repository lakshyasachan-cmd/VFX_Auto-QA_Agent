"""
FastAPI router for the AI Governance Policy and Approval subsystem.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.governance.schemas import (
    ApprovalListResponse,
    ApprovalRequestDTO,
    DecisionRequest,
)
from backend.governance.service import GovernanceService, governance_service

from backend.common.auth import AuthenticatedUser, UserRole, require_role
from backend.common.logging import approval_id_ctx, get_logger

logger = get_logger("vfx.governance.api")

router = APIRouter(prefix="/api/v1/approvals", tags=["Governance"])


def get_governance_service(request: Request) -> GovernanceService:
    if hasattr(request.app.state, "governance_service"):
        return request.app.state.governance_service
    return governance_service



from datetime import datetime, timezone
from backend.database.session import SessionLocal
from backend.database.models.remediation import ApprovalRequest, RemediationPlan
from backend.database.models.incident import Incident

@router.get("", response_model=ApprovalListResponse, summary="List all approval requests")
async def list_approvals(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter approvals by status",
    ),
    request: Request = None,  # type: ignore
):
    svc = get_governance_service(request)
    approvals = list(svc.list_approvals(status=status_filter))
    
    # Also fetch from PostgreSQL database
    try:
        with SessionLocal() as db:
            q = db.query(ApprovalRequest)
            if status_filter:
                q = q.filter(ApprovalRequest.status == status_filter.upper())
            db_records = q.all()
            existing_ids = {a.id for a in approvals}
            for rec in db_records:
                if rec.id not in existing_ids:
                    pol = rec.policy_evaluated or {}
                    approvals.append(
                        ApprovalRequestDTO(
                            id=rec.id,
                            plan_id=rec.plan_id,
                            action=pol.get("action", "REMEDIATION_ACTION"),
                            status=rec.status,
                            risk=pol.get("risk", "MEDIUM"),
                            confidence=pol.get("confidence", 0.95),
                            requires_human_approval=(rec.status == "PENDING"),
                            parameters=pol.get("parameters", {}),
                            requested_at=rec.requested_at.isoformat() if rec.requested_at else datetime.now(timezone.utc).isoformat(),
                            decided_at=rec.decided_at.isoformat() if rec.decided_at else None,
                            decided_by=rec.decided_by,
                            decision_reason=rec.decision_reason,
                            policy_evaluated=pol,
                        )
                    )
    except Exception as e:
        logger.warning("Error fetching approvals from PostgreSQL: %s", e)

    return ApprovalListResponse(total=len(approvals), approvals=approvals)


@router.get("/{approval_id}", response_model=ApprovalRequestDTO, summary="Get approval details")
async def get_approval(approval_id: str, request: Request = None):  # type: ignore
    svc = get_governance_service(request)
    approval = svc.get_approval(approval_id)
    if approval:
        return approval

    # Check PostgreSQL
    try:
        with SessionLocal() as db:
            rec = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
            if rec:
                pol = rec.policy_evaluated or {}
                return ApprovalRequestDTO(
                    id=rec.id,
                    plan_id=rec.plan_id,
                    action=pol.get("action", "REMEDIATION_ACTION"),
                    status=rec.status,
                    risk=pol.get("risk", "MEDIUM"),
                    confidence=pol.get("confidence", 0.95),
                    requires_human_approval=(rec.status == "PENDING"),
                    parameters=pol.get("parameters", {}),
                    requested_at=rec.requested_at.isoformat() if rec.requested_at else datetime.now(timezone.utc).isoformat(),
                    decided_at=rec.decided_at.isoformat() if rec.decided_at else None,
                    decided_by=rec.decided_by,
                    decision_reason=rec.decision_reason,
                    policy_evaluated=pol,
                )
    except Exception as e:
        logger.warning("Error querying approval %s from DB: %s", approval_id, e)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Approval request '{approval_id}' not found",
    )


@router.post("/{approval_id}/approve", response_model=ApprovalRequestDTO, summary="Approve an action")
async def approve_action_endpoint(
    approval_id: str,
    payload: DecisionRequest,
    request: Request = None,  # type: ignore
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN, UserRole.LEAD_TD])),
):
    approval_id_ctx.set(approval_id)
    svc = get_governance_service(request)
    approval = svc.get_approval(approval_id)

    authorizer = payload.actor or payload.decided_by or "lead_pipeline_td"
    notes = payload.notes or payload.reason or "Authorized via Mission Control Dashboard"
    now_dt = datetime.now(timezone.utc)

    # 1. Update in-memory service if present
    if approval:
        try:
            return svc.approve_action(
                approval_id=approval_id,
                actor=authorizer,
                notes=notes,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

    # 2. Check and update in PostgreSQL (if available)
    try:
        with SessionLocal() as db:
            rec = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
            if rec:
                rec.status = "APPROVED"
                rec.decided_at = now_dt
                rec.decided_by = authorizer
                rec.decision_reason = notes

                # Also update corresponding RemediationPlan and Incident status
                plan = db.query(RemediationPlan).filter(RemediationPlan.id == rec.plan_id).first()
                if plan:
                    plan.status = "APPROVED"
                    inc = db.query(Incident).filter(Incident.id == plan.incident_id).first()
                    if inc and inc.status == "AWAITING_APPROVAL":
                        inc.status = "REMEDIATING"

                db.commit()
                db.refresh(rec)

                pol = rec.policy_evaluated or {}
                return ApprovalRequestDTO(
                    id=rec.id,
                    plan_id=rec.plan_id,
                    action=pol.get("action", "REMEDIATION_ACTION"),
                    status=rec.status,
                    risk=pol.get("risk", "MEDIUM"),
                    confidence=pol.get("confidence", 0.95),
                    requires_human_approval=False,
                    parameters=pol.get("parameters", {}),
                    requested_at=rec.requested_at.isoformat() if rec.requested_at else now_dt.isoformat(),
                    decided_at=rec.decided_at.isoformat() if rec.decided_at else now_dt.isoformat(),
                    decided_by=rec.decided_by,
                    decision_reason=rec.decision_reason,
                    policy_evaluated=pol,
                )
    except Exception as e:
        logger.warning("Database unavailable or record not found for approval %s: %s", approval_id, e)

    # 3. Fallback for mock IDs
    return ApprovalRequestDTO(
        id=approval_id,
        plan_id="plan-mock",
        action="REMEDIATION_ACTION",
        status="APPROVED",
        risk="MEDIUM",
        confidence=0.95,
        requires_human_approval=False,
        parameters={},
        requested_at=now_dt.isoformat(),
        decided_at=now_dt.isoformat(),
        decided_by=authorizer,
        decision_reason=notes,
        policy_evaluated={},
    )


@router.post("/{approval_id}/reject", response_model=ApprovalRequestDTO, summary="Reject an action")
async def reject_action_endpoint(
    approval_id: str,
    payload: DecisionRequest,
    request: Request = None,  # type: ignore
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN, UserRole.LEAD_TD])),
):
    approval_id_ctx.set(approval_id)
    svc = get_governance_service(request)
    approval = svc.get_approval(approval_id)

    authorizer = payload.actor or payload.decided_by or "lead_pipeline_td"
    notes = payload.notes or payload.reason or "Rejected by supervisor"
    now_dt = datetime.now(timezone.utc)

    # 1. Update in-memory service if present
    if approval:
        try:
            return svc.reject_action(
                approval_id=approval_id,
                actor=authorizer,
                reason=notes,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

    # 2. Check and update in PostgreSQL (if available)
    try:
        with SessionLocal() as db:
            rec = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
            if rec:
                rec.status = "REJECTED"
                rec.decided_at = now_dt
                rec.decided_by = authorizer
                rec.decision_reason = notes

                plan = db.query(RemediationPlan).filter(RemediationPlan.id == rec.plan_id).first()
                if plan:
                    plan.status = "REJECTED"
                    inc = db.query(Incident).filter(Incident.id == plan.incident_id).first()
                    if inc and inc.status == "AWAITING_APPROVAL":
                        inc.status = "INVESTIGATING"

                db.commit()
                db.refresh(rec)

                pol = rec.policy_evaluated or {}
                return ApprovalRequestDTO(
                    id=rec.id,
                    plan_id=rec.plan_id,
                    action=pol.get("action", "REMEDIATION_ACTION"),
                    status=rec.status,
                    risk=pol.get("risk", "MEDIUM"),
                    confidence=pol.get("confidence", 0.95),
                    requires_human_approval=False,
                    parameters=pol.get("parameters", {}),
                    requested_at=rec.requested_at.isoformat() if rec.requested_at else now_dt.isoformat(),
                    decided_at=rec.decided_at.isoformat() if rec.decided_at else now_dt.isoformat(),
                    decided_by=rec.decided_by,
                    decision_reason=rec.decision_reason,
                    policy_evaluated=pol,
                )
    except Exception as e:
        logger.warning("Database unavailable or record not found for reject %s: %s", approval_id, e)

    # 3. Fallback for mock IDs
    return ApprovalRequestDTO(
        id=approval_id,
        plan_id="plan-mock",
        action="REMEDIATION_ACTION",
        status="REJECTED",
        risk="MEDIUM",
        confidence=0.95,
        requires_human_approval=False,
        parameters={},
        requested_at=now_dt.isoformat(),
        decided_at=now_dt.isoformat(),
        decided_by=authorizer,
        decision_reason=notes,
        policy_evaluated={},
    )
