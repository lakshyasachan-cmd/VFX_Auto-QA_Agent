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

  if (!plan) {
    return (
      <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-6 text-center text-slate-500 font-mono text-xs">
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
      setStatusFeedback("Action proposal rejected.");
    } else {
      setStatusFeedback(`Error: ${res.error}`);
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
      case "HIGH":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "MEDIUM":
        return "bg-cyan-500/20 text-cyan-300 border-cyan-500/40";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  return (
    <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5 flex flex-col space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <Wrench className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
              Proposed Remediation Plan & Human Governance Gate
            </h3>
            <p className="text-[11px] text-slate-400 font-mono">Enforced by Deterministic Policy Engine</p>
          </div>
        </div>

        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-bold ${getRiskBadge(plan.risk_level)}`}>
          {plan.risk_level} RISK LEVEL
        </span>
      </div>

      {statusFeedback && (
        <div className="text-xs font-mono px-3 py-2 rounded bg-cyan-950/40 border border-cyan-800/60 text-cyan-300">
          {statusFeedback}
        </div>
      )}

      {/* Plan Strategy Summary */}
      <div className="text-xs text-slate-300 font-mono bg-slate-900/60 border border-slate-800/80 rounded p-3 leading-relaxed">
        {plan.strategy}
      </div>

      {/* Sequenced Actions List */}
      <div className="space-y-3">
        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
          Proposed Action Items ({plan.actions.length})
        </div>

        {plan.actions.map((act, idx) => {
          const approval = approvalList.find((a) => a.action === act.action) || approvalList[0];
          const isPending = approval && approval.status === "PENDING";
          const isApproved = approval && approval.status === "APPROVED";
          const isRejected = approval && approval.status === "REJECTED";

          return (
            <div
              key={idx}
              className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
            >
              <div className="space-y-1.5 max-w-xl">
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] font-mono text-slate-500">#{idx + 1}</span>
                  <span className="font-mono font-bold text-white tracking-tight">{act.action}</span>
                  <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded border uppercase ${getRiskBadge(act.risk)}`}>
                    {act.risk}
                  </span>
                  {act.requires_human_approval && (
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                      HITL GATE
                    </span>
                  )}
                </div>
                <p className="text-slate-300 text-[11px] leading-relaxed">{act.reason}</p>

                {/* Parameters Snippet */}
                {act.parameters && Object.keys(act.parameters).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {Object.entries(act.parameters).map(([k, v]) => (
                      <span key={k} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-400">
                        {k}: <span className="text-slate-200">{String(v)}</span>
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
                      className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-mono font-bold text-[11px] flex items-center space-x-1.5 transition-colors disabled:opacity-50"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>{loadingId === approval.id ? "AUTHORIZING..." : "APPROVE"}</span>
                    </button>
                    <button
                      onClick={() => handleReject(approval.id)}
                      disabled={loadingId === approval.id}
                      className="px-3 py-1.5 rounded bg-slate-800 hover:bg-rose-900/60 hover:text-rose-300 text-slate-300 font-mono font-bold text-[11px] flex items-center space-x-1.5 border border-slate-700 transition-colors disabled:opacity-50"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>REJECT</span>
                    </button>
                  </>
                )}

                {isApproved && (
                  <div className="px-3 py-1.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono text-[11px] flex items-center space-x-1.5">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>APPROVED ({approval.decided_by || "SUPERVISOR"})</span>
                  </div>
                )}

                {isRejected && (
                  <div className="px-3 py-1.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 font-mono text-[11px] flex items-center space-x-1.5">
                    <XCircle className="w-3.5 h-3.5" />
                    <span>REJECTED</span>
                  </div>
                )}

                {!approval && (
                  <div className="px-3 py-1.5 rounded bg-slate-800 text-slate-400 font-mono text-[11px]">
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
