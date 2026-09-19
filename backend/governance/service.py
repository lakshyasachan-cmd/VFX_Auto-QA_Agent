"""
Governance Service managing the approval lifecycle and immutable audit records.
Implements:
- evaluate_policy()
- create_approval_request()
- approve_action()
- reject_action()
- modify_action()
"""

from datetime import datetime, timezone
import logging
from typing import Any, Optional
import uuid
from sqlalchemy.orm import Session

from backend.governance.policy_engine import PolicyEngine
from backend.governance.schemas import (
    ApprovalRequestDTO,
    ApprovalStatus,
    GovernanceDecision,
    PolicyEvaluationResult,
)

logger = logging.getLogger("vfx.governance.service")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceService:
    """
    Service responsible for deterministic policy enforcement, human-in-the-loop approvals,
    action modifications, and audit record generation.
    """

    def __init__(self, policy_engine: Optional[PolicyEngine] = None) -> None:
        self.policy_engine = policy_engine or PolicyEngine()
        self.approvals: dict[str, ApprovalRequestDTO] = {}
        self.audit_records: list[dict[str, Any]] = []

    def _record_audit(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str,
        previous_state: Optional[dict[str, Any]] = None,
        new_state: Optional[dict[str, Any]] = None,
        details: Optional[dict[str, Any]] = None,
        session: Optional[Session] = None,
    ) -> dict[str, Any]:
        """Record an immutable audit entry in memory and PostgreSQL if session provided."""
        record = {
            "id": str(uuid.uuid4()),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor": actor,
            "previous_state": previous_state,
            "new_state": new_state,
            "details": details or {},
            "timestamp": now_utc_iso(),
        }
        self.audit_records.append(record)

        if session is not None:
            try:
                from backend.database.models.audit import AuditLog
                log_entry = AuditLog(
                    id=record["id"],
                    entity_type=entity_type,
                    entity_id=entity_id,
                    action=action,
                    actor=actor,
                    previous_state=previous_state,
                    new_state=new_state,
                    details=details or {},
                )
                session.add(log_entry)
                session.commit()
            except Exception as e:
                logger.error(f"Failed to commit database audit log: {e}")

        return record

    def evaluate_policy(
        self,
        action: str,
        parameters: Optional[dict[str, Any]] = None,
        confidence: float = 1.0,
        risk: Optional[str] = None,
        incident_severity: str = "MEDIUM",
    ) -> PolicyEvaluationResult:
        """Deterministic policy evaluation."""
        return self.policy_engine.evaluate_policy(
            action=action,
            parameters=parameters,
            confidence=confidence,
            risk=risk,
            incident_severity=incident_severity,
        )

    def create_approval_request(
        self,
        action: Any,
        plan_id: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
        confidence: float = 1.0,
        risk: Optional[str] = None,
        incident_severity: str = "MEDIUM",
        session: Optional[Session] = None,
        incident_id: Optional[str] = None,
        source_agent: Optional[str] = None,
    ) -> ApprovalRequestDTO:
        """
        Create and evaluate an approval request for a proposed remediation action.
        Automatically sets status to AUTO_APPROVED, REJECTED, or PENDING based on policy.
        Every creation records an immutable audit entry.
        """
        effective_plan_id = plan_id or incident_id or f"plan-{uuid.uuid4()}"

        # If action is dict or object, unpack if parameters/confidence/risk not explicitly passed
        if isinstance(action, dict):
            act_name = action.get("action", "")
            params = parameters or action.get("parameters", {})
            conf = action.get("confidence", confidence)
            rsk = risk or action.get("risk")
        elif hasattr(action, "action"):
            act_name = getattr(action, "action")
            params = parameters or getattr(action, "parameters", {})
            conf = getattr(action, "confidence", confidence)
            rsk = risk or getattr(action, "risk")
        else:
            act_name = str(action)
            params = parameters or {}
            conf = confidence
            rsk = risk

        eval_result = self.evaluate_policy(
            action=act_name,
            parameters=params,
            confidence=conf,
            risk=rsk,
            incident_severity=incident_severity,
        )

        req_id = str(uuid.uuid4())
        req_time = now_utc_iso()

        if eval_result.decision == GovernanceDecision.AUTO_APPROVE:
            status = ApprovalStatus.AUTO_APPROVED.value
            decided_at = req_time
            decided_by = "policy_engine_auto"
            decision_reason = eval_result.reason
            requires_human = False
        elif eval_result.decision == GovernanceDecision.POLICY_REJECT:
            status = ApprovalStatus.REJECTED.value
            decided_at = req_time
            decided_by = "policy_engine"
            decision_reason = f"POLICY REJECTION: {eval_result.reason}"
            requires_human = False
        else:
            status = ApprovalStatus.PENDING.value
            decided_at = None
            decided_by = None
            decision_reason = None
            requires_human = True

        dto = ApprovalRequestDTO(
            id=req_id,
            plan_id=effective_plan_id,
            action=str(act_name).upper(),
            status=status,
            risk=eval_result.risk,
            confidence=round(conf, 3),
            requires_human_approval=requires_human,
            parameters=params,
            requested_at=req_time,
            decided_at=decided_at,
            decided_by=decided_by,
            decision_reason=decision_reason,
            policy_evaluated=eval_result.model_dump(mode="json"),
        )
        self.approvals[req_id] = dto

        # Record immutable audit entry
        self._record_audit(
            entity_type="ApprovalRequest",
            entity_id=req_id,
            action=f"CREATED_{status}",
            actor=decided_by or (source_agent or "system"),
            new_state={"status": status, "risk": eval_result.risk},
            details={
                "action": str(act_name).upper(),
                "policy_rule": eval_result.policy_rule,
                "reason": eval_result.reason,
            },
            session=session,
        )

        return dto

    def approve_action(
        self,
        approval_id: str,
        actor: Optional[str] = None,
        notes: Optional[str] = None,
        decided_by: Optional[str] = None,
        reason: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> ApprovalRequestDTO:
        """
        Authorize a pending approval request.
        Creates an immutable audit record.
        """
        req = self.approvals.get(approval_id)
        if not req:
            raise KeyError(f"Approval request '{approval_id}' not found.")

        if req.status in (ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value, ApprovalStatus.AUTO_APPROVED.value):
            raise ValueError(f"Cannot approve: request '{approval_id}' has already reached terminal status '{req.status}'.")

        authorizer = actor or decided_by or "human_supervisor"
        decision_notes = notes or reason or "Approved by human supervisor"

        prev_state = {"status": req.status}
        decided_time = now_utc_iso()

        req.status = ApprovalStatus.APPROVED.value
        req.decided_at = decided_time
        req.decided_by = authorizer
        req.decision_reason = decision_notes
        self.approvals[approval_id] = req

        # Record immutable audit record
        self._record_audit(
            entity_type="ApprovalRequest",
            entity_id=approval_id,
            action="APPROVED",
            actor=authorizer,
            previous_state=prev_state,
            new_state={"status": ApprovalStatus.APPROVED.value, "decided_by": authorizer},
            details={"reason": decision_notes, "action": req.action_name},
            session=session,
        )

        return req

    def reject_action(
        self,
        approval_id: str,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
        notes: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> ApprovalRequestDTO:
        """
        Reject a pending approval request.
        Creates an immutable audit record.
        """
        req = self.approvals.get(approval_id)
        if not req:
            raise KeyError(f"Approval request '{approval_id}' not found.")

        if req.status in (ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value, ApprovalStatus.AUTO_APPROVED.value):
            raise ValueError(f"Cannot reject: request '{approval_id}' has already reached terminal status '{req.status}'.")

        rejector = actor or decided_by or "human_supervisor"
        decision_reason = reason or notes or "Rejected by human supervisor"

        prev_state = {"status": req.status}
        decided_time = now_utc_iso()

        req.status = ApprovalStatus.REJECTED.value
        req.decided_at = decided_time
        req.decided_by = rejector
        req.decision_reason = decision_reason
        self.approvals[approval_id] = req

        # Record immutable audit record
        self._record_audit(
            entity_type="ApprovalRequest",
            entity_id=approval_id,
            action="REJECTED",
            actor=rejector,
            previous_state=prev_state,
            new_state={"status": ApprovalStatus.REJECTED.value, "decided_by": rejector},
            details={"reason": decision_reason, "action": req.action_name},
            session=session,
        )

        return req

    def modify_action(
        self,
        approval_id: str,
        modified_parameters: Optional[dict[str, Any]] = None,
        decided_by: Optional[str] = None,
        reason: Optional[str] = None,
        actor: Optional[str] = None,
        updated_parameters: Optional[dict[str, Any]] = None,
        updated_risk: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> ApprovalRequestDTO:
        """
        Modify the parameters of a proposed action and re-evaluate policy.
        Creates an immutable audit record of the modification.
        """
        req = self.approvals.get(approval_id)
        if not req:
            raise KeyError(f"Approval request '{approval_id}' not found.")

        effective_params = updated_parameters if updated_parameters is not None else (modified_parameters or {})
        modifier = actor or decided_by or "human_supervisor"
        mod_reason = reason or "Parameters adjusted by supervisor"

        old_params = dict(req.parameters)
        old_risk = req.risk

        merged_params = dict(old_params)
        merged_params.update(effective_params)

        # Re-evaluate policy on new parameters and optional updated risk
        new_eval = self.evaluate_policy(
            action=req.action_name,
            parameters=merged_params,
            confidence=req.confidence,
            risk=updated_risk or old_risk,
        )

        req.parameters = merged_params
        req.risk = new_eval.risk

        # If re-evaluation allows auto-approval (e.g. risk reduced to LOW with high confidence)
        if new_eval.decision == GovernanceDecision.AUTO_APPROVE:
            req.status = ApprovalStatus.AUTO_APPROVED.value
            req.decided_by = "policy_engine_auto"
        else:
            req.status = ApprovalStatus.MODIFIED.value
            req.decided_by = modifier

        req.decided_at = now_utc_iso()
        req.decision_reason = f"Modified parameters: {mod_reason}"
        req.policy_evaluated = new_eval.model_dump(mode="json")
        req.modification_history.append({
            "timestamp": req.decided_at,
            "actor": modifier,
            "reason": mod_reason,
            "old_parameters": old_params,
            "new_parameters": merged_params,
            "old_risk": old_risk,
            "new_risk": new_eval.risk,
            "re_evaluated_decision": new_eval.decision.value,
        })
        self.approvals[approval_id] = req

        # Record immutable audit record
        self._record_audit(
            entity_type="ApprovalRequest",
            entity_id=approval_id,
            action="MODIFIED",
            actor=modifier,
            previous_state={"parameters": old_params, "risk": old_risk},
            new_state={"parameters": merged_params, "risk": new_eval.risk, "status": req.status},
            details={"reason": mod_reason, "re_evaluated_rule": new_eval.policy_rule},
            session=session,
        )

        return req


    def get_approval(self, approval_id: str) -> Optional[ApprovalRequestDTO]:
        """Retrieve approval request by ID."""
        return self.approvals.get(approval_id)

    def list_approvals(self, status: Optional[str] = None) -> list[ApprovalRequestDTO]:
        """List all approval requests, optionally filtered by status."""
        items = list(self.approvals.values())
        if status:
            s_upper = status.upper()
            items = [item for item in items if item.status == s_upper]
        return items

    def get_audit_records(self, entity_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Retrieve audit log entries."""
        if entity_id:
            return [r for r in self.audit_records if r.get("entity_id") == entity_id]
        return list(self.audit_records)

    def clear(self) -> None:
        """Reset in-memory data store."""
        self.approvals.clear()
        self.audit_records.clear()


# Global singleton instance
governance_service = GovernanceService()
