"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/layout/Navbar";
import { fetchIncidents, fetchClusterHealth } from "@/lib/api";
import { IncidentSummary, ClusterNodeHealth } from "@/lib/types";
import { Activity, AlertTriangle, ShieldCheck, Cpu, HardDrive, ArrowRight, Zap, CheckCircle2 } from "lucide-react";

export default function MissionControlOverview() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [nodes, setNodes] = useState<ClusterNodeHealth[]>([]);

  useEffect(() => {
    fetchIncidents().then(setIncidents);
    fetchClusterHealth().then(setNodes);
  }, []);

  const highSeverityCount = incidents.filter((i) => i.severity === "CRITICAL" || i.severity === "HIGH").length;
  const pendingApprovalsCount = incidents.reduce(
    (acc, i) => acc + (i.approvals?.filter((a) => a.status === "PENDING").length || 0),
    0
  );

  return (
    <div className="min-h-screen flex flex-col bg-[#070b12] text-slate-100">
      <Navbar />

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {/* KPI Command Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
              <span>ACTIVE INCIDENTS</span>
              <AlertTriangle className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-white flex items-baseline space-x-2">
              <span>{incidents.length}</span>
              <span className="text-xs text-rose-400 font-normal">({highSeverityCount} Critical/High)</span>
            </div>
          </div>

          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
              <span>GOVERNANCE APPROVAL QUEUE</span>
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-cyan-400 flex items-baseline space-x-2">
              <span>{pendingApprovalsCount}</span>
              <span className="text-xs text-slate-400 font-normal">Pending HITL</span>
            </div>
          </div>

          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
              <span>CLUSTER CAPACITY</span>
              <Cpu className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-white flex items-baseline space-x-2">
              <span>91.4%</span>
              <span className="text-xs text-emerald-400 font-normal">6 Blades Active</span>
            </div>
          </div>

          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
              <span>MEAN TIME TO REPAIR (MTTR)</span>
              <Zap className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-white flex items-baseline space-x-2">
              <span>3.8 min</span>
              <span className="text-xs text-emerald-400 font-normal">-68% vs Manual</span>
            </div>
          </div>
        </div>

        {/* Active Incidents Queue */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-lg overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-900/40">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
                Live Incident Triage Feed
              </h2>
            </div>
            <span className="text-[11px] font-mono text-slate-400">Autorefreshing (1s poll)</span>
          </div>

          <div className="divide-y divide-slate-800/80">
            {incidents.map((inc) => (
              <Link
                key={inc.id}
                href={`/incidents/${inc.id}`}
                className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-850 transition-colors group block"
              >
                <div className="space-y-1 max-w-3xl">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                        inc.severity === "CRITICAL"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                          : inc.severity === "HIGH"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                          : "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                      }`}
                    >
                      {inc.severity}
                    </span>
                    <span className="font-mono font-bold text-sm text-slate-100 group-hover:text-cyan-400 transition-colors">
                      {inc.title}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 flex flex-wrap gap-x-3 gap-y-1 font-mono pt-1">
                    <span>PROJECT: <span className="text-slate-200">{inc.project}</span></span>
                    <span>SHOT: <span className="text-slate-200">{inc.shot}</span></span>
                    <span>NODE: <span className="text-slate-200">{inc.node_id || "N/A"}</span></span>
                    <span>SOURCE: <span className="text-slate-200">{inc.source_system}</span></span>
                  </div>
                </div>

                <div className="flex items-center space-x-3 flex-shrink-0">
                  <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-amber-400">
                    {inc.status}
                  </span>
                  <div className="w-8 h-8 rounded bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-400 group-hover:text-cyan-400 group-hover:border-cyan-500/40 transition-colors">
                    <ArrowRight className="w-4 h-4" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Cluster Telemetry Grid */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <HardDrive className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
                Render Node Blade Telemetry
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">Real-time GPU / Thermal monitor</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {nodes.map((node) => (
              <div key={node.node_id} className="bg-slate-900 border border-slate-800 rounded p-3 text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-slate-200">{node.node_id}</span>
                  <span
                    className={`text-[9px] font-mono px-1.5 py-0.2 rounded ${
                      node.status === "ONLINE"
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-rose-500/20 text-rose-300"
                    }`}
                  >
                    {node.status}
                  </span>
                </div>
                <div className="space-y-1 font-mono text-[11px] text-slate-400">
                  <div className="flex justify-between">
                    <span>GPU VRAM:</span>
                    <span className="text-slate-200">{node.gpu_memory_used_percent}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>TEMP:</span>
                    <span className={node.gpu_temperature_celsius > 85 ? "text-rose-400 font-bold" : "text-slate-200"}>
                      {node.gpu_temperature_celsius}°C
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>SCRATCH DISK:</span>
                    <span className="text-slate-200">{node.scratch_disk_free_gb} GB free</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
