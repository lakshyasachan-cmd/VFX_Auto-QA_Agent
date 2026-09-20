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
    <div className="min-h-screen flex flex-col bg-[#F8F9FA] text-[#202124]">
      <Navbar />

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        <div className="flex items-center justify-between border-b border-[#DADCE0] pb-4">
          <div>
            <h1 className="text-xl font-mono font-bold text-[#202124] tracking-tight flex items-center space-x-2">
              <Cpu className="w-5 h-5 text-[#1A73E8]" />
              <span>Cluster Hardware Telemetry & Agent Fleet Performance</span>
            </h1>
            <p className="text-xs text-[#5F6368] font-mono mt-1">
              Real-time monitoring across 6 render blades, GPU memory pressure, and specialist agent metrics.
            </p>
          </div>
        </div>

        {/* Agent Fleet Performance Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white border border-[#DADCE0] rounded-lg p-4 space-y-1 shadow-sm hover:border-[#BDC1C6] transition-colors">
            <div className="text-[11px] font-mono text-[#5F6368] uppercase">Supervisor Router Latency</div>
            <div className="text-2xl font-bold font-mono text-[#202124]">412 ms</div>
            <div className="text-[10px] text-[#188038] font-mono">100% triage accuracy</div>
          </div>
          <div className="bg-white border border-[#DADCE0] rounded-lg p-4 space-y-1 shadow-sm hover:border-[#BDC1C6] transition-colors">
            <div className="text-[11px] font-mono text-[#5F6368] uppercase">Specialist Execution Time</div>
            <div className="text-2xl font-bold font-mono text-[#202124]">1.84 s</div>
            <div className="text-[10px] text-[#188038] font-mono">4 specialists in parallel</div>
          </div>
          <div className="bg-white border border-[#DADCE0] rounded-lg p-4 space-y-1 shadow-sm hover:border-[#BDC1C6] transition-colors">
            <div className="text-[11px] font-mono text-[#5F6368] uppercase">Gemini Reasoning Agreement</div>
            <div className="text-2xl font-bold font-mono text-[#202124]">96.8%</div>
            <div className="text-[10px] text-[#188038] font-mono">Ground truth concordance</div>
          </div>
          <div className="bg-white border border-[#DADCE0] rounded-lg p-4 space-y-1 shadow-sm hover:border-[#BDC1C6] transition-colors">
            <div className="text-[11px] font-mono text-[#5F6368] uppercase">Policy Gate Rejections</div>
            <div className="text-2xl font-bold font-mono text-[#202124]">0 Bypass</div>
            <div className="text-[10px] text-[#188038] font-mono">100% policy enforcement</div>
          </div>
        </div>

        {/* Node Telemetry Details Table */}
        <div className="bg-white border border-[#DADCE0] rounded-lg overflow-hidden shadow-sm">
          <div className="px-5 py-3.5 border-b border-[#E8EAED] bg-[#F8F9FA] text-xs font-mono font-bold uppercase text-[#202124]">
            Node Blade Fleet Telemetry
          </div>
          <table className="w-full text-left text-xs font-mono">
            <thead className="border-b border-[#DADCE0] bg-[#F8F9FA] text-[#5F6368]">
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
            <tbody className="divide-y divide-[#E8EAED]">
              {nodes.map((n) => (
                <tr key={n.node_id} className="hover:bg-[#F8F9FA] transition-colors">
                  <td className="p-3 font-bold text-[#202124]">{n.node_id}</td>
                  <td className="p-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        n.status === "ONLINE"
                          ? "bg-[#E6F4EA] text-[#137333] border-[#CEEAD6]"
                          : "bg-[#FCE8E6] text-[#C5221F] border-[#FAD2CF]"
                      }`}
                    >
                      {n.status}
                    </span>
                  </td>
                  <td className="p-3 text-[#3C4043]">{n.gpu_utilization}%</td>
                  <td className="p-3">
                    <span className={n.gpu_memory_used_percent > 90 ? "text-[#D93025] font-bold" : "text-[#3C4043]"}>
                      {n.gpu_memory_used_percent}%
                    </span>
                  </td>
                  <td className="p-3">
                    <span className={n.gpu_temperature_celsius > 85 ? "text-[#D93025] font-bold" : "text-[#3C4043]"}>
                      {n.gpu_temperature_celsius}°C
                    </span>
                  </td>
                  <td className="p-3 text-[#3C4043]">{n.scratch_disk_free_gb} GB</td>
                  <td className="p-3 text-[#3C4043]">{n.active_jobs}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
