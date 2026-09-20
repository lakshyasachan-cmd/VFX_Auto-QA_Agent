"use client";

import React, { useEffect, useState, useCallback } from "react";
import Navbar from "@/components/layout/Navbar";
import { fetchIncidents, approveRemediationAction, rejectRemediationAction } from "@/lib/api";
import { IncidentSummary, ApprovalRequestItem } from "@/lib/types";
import { ShieldCheck, CheckCircle, XCircle } from "lucide-react";

export default function ApprovalsQueuePage() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [decisions, setDecisions] = useState<Record<string, "APPROVED" | "REJECTED">>({});
  const [feedback, setFeedback] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const loadIncidents = useCallback(() => {
    fetchIncidents().then(setIncidents);
  }, []);

  useEffect(() => {
    loadIncidents();
    try {
      const cached = localStorage.getItem("vfx_governance_decisions");
      if (cached) {
        setDecisions(JSON.parse(cached));
      }
    } catch (e) {
      // Local storage disabled or SSR
    }
  }, [loadIncidents]);

  // Collect all approvals across all incidents, applying any local decisions
  const allApprovals: Array<{ approval: ApprovalRequestItem; incident: IncidentSummary }> = [];
  incidents.forEach((inc) => {
    inc.approvals?.forEach((appr) => {
      const decidedStatus = decisions[appr.id] || appr.status;
      allApprovals.push({
        approval: { ...appr, status: decidedStatus },
        incident: inc,
      });
    });
  });

  const pendingCount = allApprovals.filter((a) => a.approval.status === "PENDING").length;

  const handleApprove = async (id: string) => {
    setLoadingId(id);
    setFeedback(null);
    const res = await approveRemediationAction(id);
    if (res.success) {
      setFeedback({ message: `✓ Action #${id.slice(0, 8)} authorized. Transferred to MCP Execution Gateway.`, type: "success" });
      
      // Update decisions state & localStorage
      const updatedDecisions = { ...decisions, [id]: "APPROVED" as const };
      setDecisions(updatedDecisions);
      try {
        localStorage.setItem("vfx_governance_decisions", JSON.stringify(updatedDecisions));
      } catch (e) {}

      // Optimistically update local incidents
      setIncidents((prev) =>
        prev.map((inc) => ({
          ...inc,
          approvals: inc.approvals?.map((a) =>
            a.id === id ? { ...a, status: "APPROVED" } : a
          ),
        }))
      );
    } else {
      setFeedback({ message: `✗ Failed: ${res.error}`, type: "error" });
    }
    setLoadingId(null);
  };

  const handleReject = async (id: string) => {
    setLoadingId(id);
    setFeedback(null);
    const res = await rejectRemediationAction(id);
    if (res.success) {
      setFeedback({ message: `✓ Action #${id.slice(0, 8)} rejected and logged.`, type: "success" });
      
      const updatedDecisions = { ...decisions, [id]: "REJECTED" as const };
      setDecisions(updatedDecisions);
      try {
        localStorage.setItem("vfx_governance_decisions", JSON.stringify(updatedDecisions));
      } catch (e) {}

      setIncidents((prev) =>
        prev.map((inc) => ({
          ...inc,
          approvals: inc.approvals?.map((a) =>
            a.id === id ? { ...a, status: "REJECTED" } : a
          ),
        }))
      );
    } else {
      setFeedback({ message: `✗ Failed: ${res.error}`, type: "error" });
    }
    setLoadingId(null);
  };

  const [filter, setFilter] = useState<"PENDING" | "RESOLVED" | "ALL">("PENDING");

  const displayedApprovals = allApprovals.filter(({ approval }) => {
    if (filter === "PENDING") return approval.status === "PENDING";
    if (filter === "RESOLVED") return approval.status === "APPROVED" || approval.status === "REJECTED";
    return true;
  });

  return (
    <div className="min-h-screen flex flex-col bg-[#F8F9FA] text-[#202124]">
      <Navbar />

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#DADCE0] pb-4">
          <div>
            <h1 className="text-xl font-mono font-bold text-[#202124] tracking-tight flex items-center space-x-2">
              <ShieldCheck className="w-5 h-5 text-[#F9AB00]" />
              <span>Human-in-the-Loop Governance Approval Queue</span>
            </h1>
            <p className="text-xs text-[#5F6368] font-mono mt-1">
              Deterministic safety gate: High-risk & production actions mandate studio supervisor authorization.
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <div className="flex bg-[#F1F3F4] border border-[#DADCE0] rounded-lg p-1 text-xs font-mono">
              <button
                onClick={() => setFilter("PENDING")}
                className={`px-3 py-1 rounded-md transition-colors ${
                  filter === "PENDING" ? "bg-white text-[#B06000] font-bold shadow-sm border border-[#DADCE0]" : "text-[#5F6368] hover:text-[#202124]"
                }`}
              >
                PENDING ({pendingCount})
              </button>
              <button
                onClick={() => setFilter("RESOLVED")}
                className={`px-3 py-1 rounded-md transition-colors ${
                  filter === "RESOLVED" ? "bg-white text-[#1A73E8] font-bold shadow-sm border border-[#DADCE0]" : "text-[#5F6368] hover:text-[#202124]"
                }`}
              >
                RESOLVED ({allApprovals.length - pendingCount})
              </button>
              <button
                onClick={() => setFilter("ALL")}
                className={`px-3 py-1 rounded-md transition-colors ${
                  filter === "ALL" ? "bg-white text-[#202124] font-bold shadow-sm border border-[#DADCE0]" : "text-[#5F6368] hover:text-[#202124]"
                }`}
              >
                ALL ({allApprovals.length})
              </button>
            </div>
          </div>
        </div>

        {feedback && (
          <div
            className={`p-3 rounded-lg border text-xs font-mono transition-all ${
              feedback.type === "success"
                ? "bg-[#E6F4EA] border-[#CEEAD6] text-[#137333]"
                : "bg-[#FCE8E6] border-[#FAD2CF] text-[#C5221F]"
            }`}
          >
            {feedback.message}
          </div>
        )}

        <div className="bg-white border border-[#DADCE0] rounded-lg overflow-hidden divide-y divide-[#E8EAED] shadow-sm">
          {displayedApprovals.length === 0 ? (
            <div className="p-10 text-center text-[#80868B] font-mono text-xs">
              {filter === "PENDING"
                ? "All actions have been governed! No pending decisions remaining."
                : "No governance approvals found matching the selected filter."}
            </div>
          ) : (
            displayedApprovals.map(({ approval, incident }) => (
              <div key={approval.id} className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-[#F8F9FA] transition-colors">
                <div className="space-y-2 max-w-2xl">
                  <div className="flex items-center space-x-2.5 flex-wrap gap-y-1">
                    <span className="text-xs font-mono font-bold text-[#202124]">{approval.action}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#FEF7E0] text-[#B06000] border border-[#FEEFC3] font-bold uppercase">
                      {approval.risk} RISK
                    </span>
                    <span className="text-[10px] font-mono text-[#80868B]">
                      CONFIDENCE: {Math.round(approval.confidence * 100)}%
                    </span>
                  </div>

                  <div className="text-xs text-[#5F6368] font-mono">
                    TARGET INCIDENT:{" "}
                    <span className="text-[#1A73E8] font-bold">{incident.title}</span>{" "}
                    ({incident.project} / {incident.shot})
                  </div>

                  <div className="bg-[#F8F9FA] border border-[#E8EAED] rounded p-2 text-xs font-mono text-[#3C4043] break-all">
                    PARAMS: {JSON.stringify(approval.parameters)}
                  </div>
                </div>

                <div className="flex items-center space-x-3 self-end md:self-center">
                  {approval.status === "PENDING" ? (
                    <>
                      <button
                        onClick={() => handleApprove(approval.id)}
                        disabled={loadingId === approval.id}
                        className="px-4 py-2 rounded-md bg-[#188038] hover:bg-[#137333] disabled:opacity-50 disabled:cursor-wait text-white font-mono font-bold text-xs flex items-center space-x-1.5 shadow-sm transition-colors"
                      >
                        <CheckCircle className="w-4 h-4" />
                        <span>{loadingId === approval.id ? "PROCESSING..." : "APPROVE"}</span>
                      </button>
                      <button
                        onClick={() => handleReject(approval.id)}
                        disabled={loadingId === approval.id}
                        className="px-4 py-2 rounded-md bg-white hover:bg-[#FCE8E6] disabled:opacity-50 disabled:cursor-wait text-[#D93025] hover:text-[#C5221F] border border-[#DADCE0] hover:border-[#FAD2CF] font-mono font-bold text-xs flex items-center space-x-1.5 shadow-sm transition-colors"
                      >
                        <XCircle className="w-4 h-4" />
                        <span>REJECT</span>
                      </button>
                    </>
                  ) : (
                    <span
                      className={`px-3 py-1.5 rounded border font-mono text-xs font-bold uppercase ${
                        approval.status === "APPROVED"
                          ? "bg-[#E6F4EA] border-[#CEEAD6] text-[#137333]"
                          : "bg-[#FCE8E6] border-[#FAD2CF] text-[#C5221F]"
                      }`}
                    >
                      {approval.status}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
