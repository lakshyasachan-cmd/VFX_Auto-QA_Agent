"use client";

import React, { useState } from "react";
import { RemediationPlanItem, ApprovalRequestItem } from "@/lib/types";
import { Wrench, ShieldAlert, CheckCircle, XCircle, Clock, ShieldCheck } from "lucide-react";
import { approveRemediationAction, rejectRemediationAction } from "@/lib/api";

interface Props {
  plan?: RemediationPlanItem;
  approvals: ApprovalRequestItem[];
}

export default function RemediationPanel({ plan, approvals }: Props) {
  const [approvalList, setApprovalList] = useState<ApprovalRequestItem[]>(approvals);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [statusFeedback, setStatusFeedback] = useState<string | null>(null);

  React.useEffect(() => {
    try {
      const cached = localStorage.getItem("vfx_governance_decisions");
      if (cached) {
        const decisions = JSON.parse(cached);
        setApprovalList(
          approvals.map((a) => (decisions[a.id] ? { ...a, status: decisions[a.id] } : a))
        );
        return;
      }
    } catch (e) {}
    setApprovalList(approvals);
  }, [approvals]);

  if (!plan) {
    return (
      <div className="bg-white border border-[#DADCE0] rounded-lg p-6 text-center text-[#80868B] font-mono text-xs shadow-sm">
        Remediation strategy planning in progress...
      </div>
    );
  }

  const handleApprove = async (approvalId: string) => {
    setLoadingId(approvalId);
    setStatusFeedback(null);
    const res = await approveRemediationAction(approvalId);
    setLoadingId(null);
    if (res.success) {
      setApprovalList((prev) =>
        prev.map((a) => (a.id === approvalId ? { ...a, status: "APPROVED", decided_by: "lead_vfx_supervisor" } : a))
      );
      try {
        const cached = localStorage.getItem("vfx_governance_decisions");
        const dec = cached ? JSON.parse(cached) : {};
        dec[approvalId] = "APPROVED";
        localStorage.setItem("vfx_governance_decisions", JSON.stringify(dec));
      } catch (e) {}
      setStatusFeedback("Action approved and dispatched to MCP Execution Gateway.");
    } else {
      setStatusFeedback(`Error: ${res.error}`);
    }
  };

  const handleReject = async (approvalId: string) => {
    setLoadingId(approvalId);
    setStatusFeedback(null);
    const res = await rejectRemediationAction(approvalId);
    setLoadingId(null);
    if (res.success) {
      setApprovalList((prev) =>
        prev.map((a) => (a.id === approvalId ? { ...a, status: "REJECTED", decided_by: "lead_vfx_supervisor" } : a))
      );
      try {
        const cached = localStorage.getItem("vfx_governance_decisions");
        const dec = cached ? JSON.parse(cached) : {};
        dec[approvalId] = "REJECTED";
        localStorage.setItem("vfx_governance_decisions", JSON.stringify(dec));
      } catch (e) {}
      setStatusFeedback("Action proposal rejected.");
    } else {
      setStatusFeedback(`Error: ${res.error}`);
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case "CRITICAL":
        return "bg-[#FCE8E6] text-[#C5221F] border border-[#FAD2CF]";
      case "HIGH":
        return "bg-[#FEF7E0] text-[#B06000] border border-[#FEEFC3]";
      case "MEDIUM":
        return "bg-[#E8F0FE] text-[#1A73E8] border border-[#D2E3FC]";
      default:
        return "bg-[#F1F3F4] text-[#5F6368] border border-[#DADCE0]";
    }
  };

  return (
    <div className="bg-white border border-[#DADCE0] rounded-lg p-5 flex flex-col space-y-4 shadow-sm">
      <div className="flex items-center justify-between border-b border-[#E8EAED] pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#FEF7E0] border border-[#FEEFC3] flex items-center justify-center text-[#F9AB00]">
            <Wrench className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-wider text-[#202124] uppercase">
              Proposed Remediation Plan & Human Governance Gate
            </h3>
            <p className="text-[11px] text-[#5F6368] font-mono">Enforced by Deterministic Policy Engine</p>
          </div>
        </div>

        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-bold ${getRiskBadge(plan.risk_level)}`}>
          {plan.risk_level} RISK LEVEL
        </span>
      </div>

      {statusFeedback && (
        <div className="text-xs font-mono px-3 py-2 rounded-lg bg-[#E6F4EA] border border-[#CEEAD6] text-[#137333]">
          {statusFeedback}
        </div>
      )}

      {/* Plan Strategy Summary */}
      <div className="text-xs text-[#3C4043] font-mono bg-[#F8F9FA] border border-[#DADCE0] rounded-lg p-3 leading-relaxed">
        {plan.strategy}
      </div>

      {/* Sequenced Actions List */}
      <div className="space-y-3">
        <div className="text-[10px] font-mono uppercase tracking-wider text-[#5F6368] font-semibold">
          Proposed Action Items ({plan.actions.length})
        </div>

        {plan.actions.map((act, idx) => {
          const approval = approvalList.find((a) => a.action === act.action);
          const isPending = approval && approval.status === "PENDING";
          const isApproved = approval && approval.status === "APPROVED";
          const isRejected = approval && approval.status === "REJECTED";

          return (
            <div
              key={idx}
              className="bg-[#F8F9FA] border border-[#DADCE0] rounded-lg p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
            >
              <div className="space-y-1.5 max-w-xl">
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] font-mono text-[#80868B]">#{idx + 1}</span>
                  <span className="font-mono font-bold text-[#202124] tracking-tight">{act.action}</span>
                  <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded border uppercase ${getRiskBadge(act.risk)}`}>
                    {act.risk}
                  </span>
                  {act.requires_human_approval && (
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-[#FEF7E0] text-[#B06000] border border-[#FEEFC3]">
                      HITL GATE
                    </span>
                  )}
                </div>
                <p className="text-[#5F6368] text-[11px] leading-relaxed">{act.reason}</p>

                {/* Parameters Snippet */}
                {act.parameters && Object.keys(act.parameters).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {Object.entries(act.parameters).map(([k, v]) => (
                      <span key={k} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white border border-[#DADCE0] text-[#5F6368]">
                        {k}: <span className="text-[#202124] font-medium">{String(v)}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Controls / Status */}
              <div className="flex items-center space-x-2 flex-shrink-0">
                {isPending && (
                  <>
                    <button
                      onClick={() => handleApprove(approval.id)}
                      disabled={loadingId === approval.id}
                      className="px-3 py-1.5 rounded-md bg-[#188038] hover:bg-[#137333] text-white font-mono font-bold text-[11px] flex items-center space-x-1.5 transition-colors disabled:opacity-50 shadow-sm"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>{loadingId === approval.id ? "AUTHORIZING..." : "APPROVE"}</span>
                    </button>
                    <button
                      onClick={() => handleReject(approval.id)}
                      disabled={loadingId === approval.id}
                      className="px-3 py-1.5 rounded-md bg-white hover:bg-[#FCE8E6] hover:text-[#C5221F] text-[#D93025] font-mono font-bold text-[11px] flex items-center space-x-1.5 border border-[#DADCE0] hover:border-[#FAD2CF] transition-colors disabled:opacity-50 shadow-sm"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>REJECT</span>
                    </button>
                  </>
                )}

                {isApproved && (
                  <div className="px-3 py-1.5 rounded-md bg-[#E6F4EA] border border-[#CEEAD6] text-[#137333] font-mono text-[11px] flex items-center space-x-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-[#188038]" />
                    <span>APPROVED ({approval.decided_by || "SUPERVISOR"})</span>
                  </div>
                )}

                {isRejected && (
                  <div className="px-3 py-1.5 rounded-md bg-[#FCE8E6] border border-[#FAD2CF] text-[#C5221F] font-mono text-[11px] flex items-center space-x-1.5">
                    <XCircle className="w-3.5 h-3.5" />
                    <span>REJECTED</span>
                  </div>
                )}

                {!approval && (
                  <div className="px-3 py-1.5 rounded-md bg-[#F1F3F4] text-[#5F6368] border border-[#DADCE0] font-mono text-[11px]">
                    AUTO-GOVERNED
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
