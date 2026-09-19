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
    approvals = svc.list_approvals(status=status_filter)
    return ApprovalListResponse(total=len(approvals), approvals=approvals)


@router.get("/{approval_id}", response_model=ApprovalRequestDTO, summary="Get approval details")
async def get_approval(approval_id: str, request: Request = None):  # type: ignore
    svc = get_governance_service(request)
    approval = svc.get_approval(approval_id)
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found",
        )
    return approval


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
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found",
        )

    try:
        updated = svc.approve_action(
            approval_id=approval_id,
            actor=payload.actor,
            notes=payload.notes,
        )
        return updated
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
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
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found",
        )

    try:
        updated = svc.reject_action(
            approval_id=approval_id,
            actor=payload.actor,
            reason=payload.notes or "Rejected by human supervisor",
        )
        return updated
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
