"use client";

import React, { useEffect, useState } from "react";
import Navbar from "@/components/layout/Navbar";
import IncidentPipelineTrace from "@/components/incidents/IncidentPipelineTrace";
import EvidenceViewer from "@/components/incidents/EvidenceViewer";
import RootCausePanel from "@/components/incidents/RootCausePanel";
import RemediationPanel from "@/components/remediation/RemediationPanel";
import ExecutionTimeline from "@/components/mcp/ExecutionTimeline";
import { fetchIncidentById } from "@/lib/api";
import { IncidentSummary } from "@/lib/types";
import { ArrowLeft, Clock, ShieldAlert, Layers, Terminal } from "lucide-react";
import Link from "next/link";

export default function IncidentDetailPage({ params }: { params: { id: string } }) {
  const [incident, setIncident] = useState<IncidentSummary | null>(null);

  useEffect(() => {
    fetchIncidentById(params.id).then(setIncident);
  }, [params.id]);

  if (!incident) {
    return (
      <div className="min-h-screen bg-[#070b12] text-slate-100 flex flex-col">
        <Navbar />
        <div className="p-12 text-center text-slate-400 font-mono">
          Loading incident context {params.id}...
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#070b12] text-slate-100 pb-12">
      <Navbar />

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {/* Navigation Breadcrumbs & Incident Title */}
        <div className="space-y-2">
          <Link href="/" className="inline-flex items-center space-x-1.5 text-xs font-mono text-cyan-400 hover:text-cyan-300">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Live Incident Feed</span>
          </Link>

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div className="space-y-1">
              <div className="flex items-center space-x-2.5">
                <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 text-xs font-mono font-bold">
                  {incident.severity}
                </span>
                <h1 className="text-xl font-mono font-bold text-white tracking-tight">{incident.title}</h1>
              </div>
              <p className="text-xs text-slate-400 font-mono max-w-3xl leading-relaxed">{incident.description}</p>
            </div>

            <div className="flex items-center space-x-3 text-xs font-mono">
              <div className="bg-slate-900 border border-slate-800 px-3 py-1.5 rounded">
                <span className="text-slate-500 block text-[10px]">CORRELATION ID</span>
                <span className="text-slate-200">{incident.correlation_id}</span>
              </div>
              <div className="bg-slate-900 border border-slate-800 px-3 py-1.5 rounded">
                <span className="text-slate-500 block text-[10px]">STATUS</span>
                <span className="text-amber-400 font-bold">{incident.status}</span>
              </div>
            </div>
          </div>
        </div>

        {/* 1. Visual Pipeline Trace */}
        <IncidentPipelineTrace />

        {/* 2. Main Investigation Workspace (Evidence on left, Reasoning on right) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <EvidenceViewer evidence={incident.evidence} />
          <RootCausePanel reasoning={incident.reasoning} />
        </div>

        {/* 3. Remediation & Governance Section */}
        <RemediationPanel plan={incident.remediation_plan} approvals={incident.approvals} />

        {/* 4. Precedents & Execution Audit Trail */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Precedents */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
                Historical Incident Precedents ({incident.precedents?.length || 0})
              </span>
              <span className="text-[10px] font-mono text-slate-400">PostgreSQL Vector Precedent Matcher</span>
            </div>
            <div className="space-y-2">
              {incident.precedents?.map((prec, i) => (
                <div key={i} className="bg-slate-900 border border-slate-800 rounded p-3 text-xs space-y-1">
                  <div className="flex items-center justify-between font-mono">
                    <span className="font-bold text-slate-200">{prec.title}</span>
                    <span className="text-emerald-400 text-[11px]">{Math.round(prec.similarity * 100)}% MATCH</span>
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono">
                    RESOLUTION: <span className="text-slate-300">{prec.resolution}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono">
                    HISTORICAL SUCCESS RATE: <span className="text-emerald-400 font-bold">{Math.round(prec.success_rate * 100)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Execution Timeline */}
          <ExecutionTimeline executions={incident.executions} />
        </div>
      </main>
    </div>
  );
}
