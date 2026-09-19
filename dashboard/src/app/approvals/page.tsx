"use client";

import React, { useEffect, useState } from "react";
import Navbar from "@/components/layout/Navbar";
import { fetchIncidents, approveRemediationAction, rejectRemediationAction } from "@/lib/api";
import { IncidentSummary, ApprovalRequestItem } from "@/lib/types";
import { ShieldCheck, CheckCircle, XCircle, Clock, AlertTriangle } from "lucide-react";

export default function ApprovalsQueuePage() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    fetchIncidents().then(setIncidents);
  }, []);

  // Collect all approvals across incidents
  const allApprovals: Array<{ approval: ApprovalRequestItem; incident: IncidentSummary }> = [];
  incidents.forEach((inc) => {
    inc.approvals?.forEach((appr) => {
      allApprovals.push({ approval: appr, incident: inc });
    });
  });

  const handleApprove = async (id: string) => {
    const res = await approveRemediationAction(id);
    if (res.success) {
      setFeedback(`Authorized action #${id}. Transferred to MCP Execution Gateway.`);
    }
  };

  const handleReject = async (id: string) => {
    const res = await rejectRemediationAction(id);
    if (res.success) {
      setFeedback(`Rejected action proposal #${id}.`);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#070b12] text-slate-100">
      <Navbar />

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h1 className="text-xl font-mono font-bold text-white tracking-tight flex items-center space-x-2">
              <ShieldCheck className="w-5 h-5 text-amber-400" />
              <span>Human-in-the-Loop Governance Approval Queue</span>
            </h1>
            <p className="text-xs text-slate-400 font-mono mt-1">
              Deterministic safety gate: High-risk & production actions mandate studio supervisor authorization.
            </p>
          </div>
          <span className="px-3 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono text-xs">
            {allApprovals.filter((a) => a.approval.status === "PENDING").length} PENDING DECISIONS
          </span>
        </div>

        {feedback && (
          <div className="p-3 rounded bg-cyan-950/60 border border-cyan-800 text-cyan-300 text-xs font-mono">
            {feedback}
          </div>
        )}

        <div className="bg-[#0f172a] border border-slate-800 rounded-lg overflow-hidden divide-y divide-slate-800">
          {allApprovals.map(({ approval, incident }) => (
            <div key={approval.id} className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-2 max-w-2xl">
                <div className="flex items-center space-x-2.5">
                  <span className="text-xs font-mono font-bold text-white">{approval.action}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold uppercase">
                    {approval.risk} RISK
                  </span>
                  <span className="text-[10px] font-mono text-slate-400">
                    CONFIDENCE: {Math.round(approval.confidence * 100)}%
                  </span>
                </div>

                <div className="text-xs text-slate-300 font-mono">
                  TARGET INCIDENT: <span className="text-cyan-400 font-bold">{incident.title}</span> ({incident.project} / {incident.shot})
                </div>

                <div className="bg-slate-950 border border-slate-800/80 rounded p-2 text-xs font-mono text-slate-400">
                  PARAMS: {JSON.stringify(approval.parameters)}
                </div>
              </div>

              <div className="flex items-center space-x-3">
                {approval.status === "PENDING" ? (
                  <>
                    <button
                      onClick={() => handleApprove(approval.id)}
                      className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-mono font-bold text-xs flex items-center space-x-1.5 shadow"
                    >
                      <CheckCircle className="w-4 h-4" />
                      <span>APPROVE ACTION</span>
                    </button>
                    <button
                      onClick={() => handleReject(approval.id)}
                      className="px-4 py-2 rounded bg-slate-800 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-700 font-mono font-bold text-xs flex items-center space-x-1.5"
                    >
                      <XCircle className="w-4 h-4" />
                      <span>REJECT</span>
                    </button>
                  </>
                ) : (
                  <span className="px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-slate-400 font-mono text-xs">
                    STATUS: {approval.status}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
