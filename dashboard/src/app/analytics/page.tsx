"use client";

import React, { useEffect, useState } from "react";
import Navbar from "@/components/layout/Navbar";
import { fetchClusterHealth } from "@/lib/api";
import { ClusterNodeHealth } from "@/lib/types";
import { Cpu, HardDrive, Zap, CheckCircle2, ShieldAlert } from "lucide-react";

export default function AnalyticsHealthPage() {
  const [nodes, setNodes] = useState<ClusterNodeHealth[]>([]);

  useEffect(() => {
    fetchClusterHealth().then(setNodes);
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-[#070b12] text-slate-100">
      <Navbar />

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h1 className="text-xl font-mono font-bold text-white tracking-tight flex items-center space-x-2">
              <Cpu className="w-5 h-5 text-cyan-400" />
              <span>Cluster Hardware Telemetry & Agent Fleet Performance</span>
            </h1>
            <p className="text-xs text-slate-400 font-mono mt-1">
              Real-time monitoring across 6 render blades, GPU memory pressure, and specialist agent metrics.
            </p>
          </div>
        </div>

        {/* Agent Fleet Performance Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4 space-y-1">
            <div className="text-[11px] font-mono text-slate-400 uppercase">Supervisor Router Latency</div>
            <div className="text-2xl font-bold font-mono text-white">412 ms</div>
            <div className="text-[10px] text-emerald-400 font-mono">100% triage accuracy</div>
          </div>
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4 space-y-1">
            <div className="text-[11px] font-mono text-slate-400 uppercase">Specialist Execution Time</div>
            <div className="text-2xl font-bold font-mono text-white">1.84 s</div>
            <div className="text-[10px] text-emerald-400 font-mono">4 specialists in parallel</div>
          </div>
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4 space-y-1">
            <div className="text-[11px] font-mono text-slate-400 uppercase">Gemini Reasoning Agreement</div>
            <div className="text-2xl font-bold font-mono text-white">96.8%</div>
            <div className="text-[10px] text-emerald-400 font-mono">Ground truth concordance</div>
          </div>
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4 space-y-1">
            <div className="text-[11px] font-mono text-slate-400 uppercase">Policy Gate Rejections</div>
            <div className="text-2xl font-bold font-mono text-white">0 Bypass</div>
            <div className="text-[10px] text-emerald-400 font-mono">100% policy enforcement</div>
          </div>
        </div>

        {/* Node Telemetry Details Table */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-lg overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-800 bg-slate-900/40 text-xs font-mono font-bold uppercase text-slate-200">
            Node Blade Fleet Telemetry
          </div>
          <table className="w-full text-left text-xs font-mono">
            <thead className="border-b border-slate-800 bg-slate-950/60 text-slate-400">
              <tr>
                <th className="p-3">NODE ID</th>
                <th className="p-3">STATUS</th>
                <th className="p-3">GPU LOAD</th>
                <th className="p-3">VRAM USAGE</th>
                <th className="p-3">TEMP</th>
                <th className="p-3">SCRATCH DISK</th>
                <th className="p-3">ACTIVE JOBS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {nodes.map((n) => (
                <tr key={n.node_id} className="hover:bg-slate-900/40 transition-colors">
                  <td className="p-3 font-bold text-white">{n.node_id}</td>
                  <td className="p-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        n.status === "ONLINE"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-rose-500/20 text-rose-300"
                      }`}
                    >
                      {n.status}
                    </span>
                  </td>
                  <td className="p-3 text-slate-300">{n.gpu_utilization}%</td>
                  <td className="p-3">
                    <span className={n.gpu_memory_used_percent > 90 ? "text-rose-400 font-bold" : "text-slate-300"}>
                      {n.gpu_memory_used_percent}%
                    </span>
                  </td>
                  <td className="p-3">
                    <span className={n.gpu_temperature_celsius > 85 ? "text-rose-400 font-bold" : "text-slate-300"}>
                      {n.gpu_temperature_celsius}°C
                    </span>
                  </td>
                  <td className="p-3 text-slate-300">{n.scratch_disk_free_gb} GB</td>
                  <td className="p-3 text-slate-300">{n.active_jobs}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
