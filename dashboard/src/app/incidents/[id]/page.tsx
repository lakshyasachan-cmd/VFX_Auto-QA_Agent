"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/layout/Navbar";
import EvidenceViewer from "@/components/incidents/EvidenceViewer";
import RootCausePanel from "@/components/incidents/RootCausePanel";
import RemediationPanel from "@/components/remediation/RemediationPanel";
import ExecutionTimeline from "@/components/mcp/ExecutionTimeline";
import { fetchIncidentById } from "@/lib/api";
import { IncidentSummary } from "@/lib/types";
import { ArrowLeft } from "lucide-react";

export default function IncidentDetailPage({ params }: { params: { id: string } }) {
  const [incident, setIncident] = useState<IncidentSummary | null>(null);

  useEffect(() => {
    fetchIncidentById(params.id).then(setIncident);
  }, [params.id]);

  if (!incident) {
    return (
      <div className="min-h-screen bg-[#F8F9FA] text-[#202124] flex flex-col">
        <Navbar />
        <div className="p-12 text-center text-[#5F6368] font-mono">
          Loading incident context {params.id}...
        </div>
      </div>
    );
  }

  const severityBadgeClass =
    incident.severity === "CRITICAL"
      ? "bg-[#FCE8E6] text-[#C5221F] border border-[#FAD2CF]"
      : incident.severity === "HIGH"
      ? "bg-[#FEF7E0] text-[#B06000] border border-[#FEEFC3]"
      : "bg-[#E8F0FE] text-[#1A73E8] border border-[#D2E3FC]";

  return (
    <div className="min-h-screen flex flex-col bg-[#F8F9FA] text-[#202124] pb-12">
      <Navbar />
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        <div className="space-y-3">
          <Link
            href="/"
            className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-lg bg-white border border-[#DADCE0] text-xs font-medium text-[#3C4043] hover:text-[#1A73E8] hover:bg-[#F8F9FA] hover:border-[#BDC1C6] shadow-sm transition-all group w-fit"
          >
            <div className="w-5 h-5 rounded-full bg-[#F1F3F4] group-hover:bg-[#E8F0FE] flex items-center justify-center transition-colors">
              <ArrowLeft className="w-3 h-3 text-[#5F6368] group-hover:text-[#1A73E8] group-hover:-translate-x-0.5 transition-all" />
            </div>
            <span>Back to Live Incident Feed</span>
          </Link>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#DADCE0] pb-4">
            <div className="space-y-1">
              <div className="flex items-center space-x-2.5">
                <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold uppercase ${severityBadgeClass}`}>
                  {incident.severity}
                </span>
                <h1 className="text-xl font-mono font-bold text-[#202124] tracking-tight">{incident.title}</h1>
              </div>
              <p className="text-xs text-[#5F6368] font-mono max-w-3xl leading-relaxed">{incident.description}</p>
            </div>
            <div className="flex items-center space-x-3 text-xs font-mono">
              <div className="bg-white border border-[#DADCE0] px-3 py-1.5 rounded-lg shadow-sm">
                <span className="text-[#80868B] block text-[10px]">CORRELATION ID</span>
                <span className="text-[#202124] font-medium">{incident.correlation_id}</span>
              </div>
              <div className="bg-white border border-[#DADCE0] px-3 py-1.5 rounded-lg shadow-sm">
                <span className="text-[#80868B] block text-[10px]">STATUS</span>
                <span className="text-[#B06000] font-bold">{incident.status}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <EvidenceViewer evidence={incident.evidence} />
          <RootCausePanel reasoning={incident.reasoning} />
        </div>

        <RemediationPanel plan={incident.remediation_plan} approvals={incident.approvals} />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white border border-[#DADCE0] rounded-lg p-5 space-y-3 shadow-sm">
            <div className="flex items-center justify-between border-b border-[#E8EAED] pb-3">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#202124]">
                Historical Precedents ({incident.precedents?.length || 0})
              </span>
              <span className="text-[10px] font-mono text-[#5F6368]">PostgreSQL Precedent Matcher</span>
            </div>
            <div className="space-y-2">
              {incident.precedents?.map((prec, i) => (
                <div key={i} className="bg-[#F8F9FA] border border-[#DADCE0] rounded-lg p-3 text-xs space-y-1">
                  <div className="flex items-center justify-between font-mono">
                    <span className="font-bold text-[#202124]">{prec.title}</span>
                    <span className="text-[#188038] text-[11px] font-semibold">{Math.round(prec.similarity * 100)}% MATCH</span>
                  </div>
                  <div className="text-[11px] text-[#5F6368] font-mono">
                    RESOLUTION: <span className="text-[#202124]">{prec.resolution}</span>
                  </div>
                  <div className="text-[10px] text-[#80868B] font-mono">
                    SUCCESS RATE: <span className="text-[#188038] font-bold">{Math.round(prec.success_rate * 100)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <ExecutionTimeline executions={incident.executions} />
        </div>
      </main>
    </div>
  );
}
