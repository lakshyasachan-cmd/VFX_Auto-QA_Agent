"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/layout/Navbar";
import {
  fetchClusterHealth,
  fetchIncidents,
  subscribeIncidentStream,
  triggerSimulationScenario,
} from "@/lib/api";
import { ClusterNodeHealth, IncidentSummary } from "@/lib/types";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Cpu,
  Play,
  Radio,
  ShieldCheck,
  Zap,
} from "lucide-react";

export default function MissionControlOverview() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [nodes, setNodes] = useState<ClusterNodeHealth[]>([]);
  const [isLiveConnected, setIsLiveConnected] = useState<boolean>(false);
  const [triggering, setTriggering] = useState<boolean>(false);
  const [selectedScenario, setSelectedScenario] = useState<string>("gpu_oom");

  useEffect(() => {
    // Initial fetch
    fetchIncidents().then(setIncidents);
    fetchClusterHealth().then(setNodes);

    // Periodic poll for cluster telemetry
    const pollInterval = setInterval(() => {
      fetchClusterHealth().then(setNodes);
    }, 5000);

    // Real-Time Server-Sent Events (SSE) live incident subscription
    const unsubscribe = subscribeIncidentStream((newIncident) => {
      setIsLiveConnected(true);
      setIncidents((prev) => {
        const existingIdx = prev.findIndex((i) => i.id === newIncident.id);
        if (existingIdx >= 0) {
          const updated = [...prev];
          updated[existingIdx] = newIncident;
          return updated;
        }
        return [newIncident, ...prev];
      });
    });

    return () => {
      clearInterval(pollInterval);
      unsubscribe();
    };
  }, []);

  const handleTriggerScenario = async () => {
    setTriggering(true);
    try {
      await triggerSimulationScenario(selectedScenario);
      // Refetch incidents shortly after trigger
      setTimeout(() => {
        fetchIncidents().then(setIncidents);
        setTriggering(false);
      }, 1200);
    } catch (e) {
      setTriggering(false);
    }
  };

  const highSeverityCount = incidents.filter(
    (i) => i.severity === "CRITICAL" || i.severity === "HIGH"
  ).length;
  const pendingApprovalsCount = incidents.reduce(
    (acc, i) => acc + (i.approvals?.filter((a) => a.status === "PENDING").length || 0),
    0
  );

  return (
    <div className="min-h-screen flex flex-col bg-[#F8F9FA] text-[#202124]">
      <Navbar />

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {/* KPI Command Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white border border-[#DADCE0] rounded-lg p-4 shadow-sm hover:border-[#BDC1C6] transition-colors">
            <div className="flex items-center justify-between text-[#5F6368] text-xs font-mono mb-2">
              <span>ACTIVE INCIDENTS</span>
              <AlertTriangle className="w-4 h-4 text-[#F9AB00]" />
            </div>
            <div className="text-2xl font-bold font-mono text-[#202124] flex items-baseline space-x-2">
              <span>{incidents.length}</span>
              <span className="text-xs text-[#D93025] font-normal">
                ({highSeverityCount} Critical/High)
              </span>
            </div>
          </div>

          <div className="bg-white border border-[#DADCE0] rounded-lg p-4 shadow-sm hover:border-[#BDC1C6] transition-colors">
            <div className="flex items-center justify-between text-[#5F6368] text-xs font-mono mb-2">
              <span>GOVERNANCE APPROVAL QUEUE</span>
              <ShieldCheck className="w-4 h-4 text-[#1A73E8]" />
            </div>
            <div className="text-2xl font-bold font-mono text-[#1A73E8] flex items-baseline space-x-2">
              <span>{pendingApprovalsCount}</span>
              <span className="text-xs text-[#5F6368] font-normal">Pending HITL</span>
            </div>
          </div>

          <div className="bg-white border border-[#DADCE0] rounded-lg p-4 shadow-sm hover:border-[#BDC1C6] transition-colors">
            <div className="flex items-center justify-between text-[#5F6368] text-xs font-mono mb-2">
              <span>ACTIVE COMPUTE NODES</span>
              <Cpu className="w-4 h-4 text-[#1A73E8]" />
            </div>
            <div className="text-2xl font-bold font-mono text-[#202124] flex items-baseline space-x-2">
              <span>{nodes.length} Blades</span>
              <span className="text-xs text-[#188038] font-normal">Live Telemetry</span>
            </div>
          </div>

          <div className="bg-white border border-[#DADCE0] rounded-lg p-4 shadow-sm hover:border-[#BDC1C6] transition-colors">
            <div className="flex items-center justify-between text-[#5F6368] text-xs font-mono mb-2">
              <span>AI REASONING ENGINE</span>
              <Zap className="w-4 h-4 text-[#F9AB00]" />
            </div>
            <div className="text-2xl font-bold font-mono text-[#202124] flex items-baseline space-x-2">
              <span>Gemini 2.5</span>
              <span className="text-xs text-[#188038] font-normal">ADK Multi-Agent</span>
            </div>
          </div>
        </div>

        {/* Live Simulation Control Bar */}
        <div className="bg-white border border-[#DADCE0] rounded-lg p-4 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-[#E8F0FE] rounded-lg border border-[#D2E3FC] text-[#1A73E8]">
              <Radio className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-[#202124]">
                  Real-Time Event Stream
                </h3>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono bg-[#E6F4EA] text-[#137333] border border-[#CEEAD6]">
                  ● FASTAPI LIVE (PORT 8001)
                </span>
              </div>
              <p className="text-[11px] text-[#5F6368] font-mono mt-0.5">
                Connected to PostgreSQL database & Gemini 2.5 Flash reasoning pipeline.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3 w-full md:w-auto">
            <select
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              className="bg-white border border-[#DADCE0] text-[#202124] text-xs font-mono px-3 py-2 rounded focus:outline-none focus:border-[#1A73E8] focus:ring-1 focus:ring-[#1A73E8]"
            >
              <option value="gpu_oom">Scenario: GPU Out of Memory (Exit 137)</option>
              <option value="missing_frames">Scenario: V-Ray Dropped Frames</option>
              <option value="corrupted_alembic">Scenario: Corrupted Point Cache</option>
              <option value="node_thermal">Scenario: Blade Thermal Overheat</option>
            </select>

            <button
              onClick={handleTriggerScenario}
              disabled={triggering}
              className="px-4 py-2 bg-[#1A73E8] hover:bg-[#1557B0] disabled:opacity-50 text-white text-xs font-mono font-bold rounded-md flex items-center space-x-1.5 shadow-sm transition-colors whitespace-nowrap"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{triggering ? "DISPATCHING..." : "DISPATCH SIMULATION"}</span>
            </button>
          </div>
        </div>

        {/* Active Incidents Queue */}
        <div className="bg-white border border-[#DADCE0] rounded-lg overflow-hidden shadow-sm">
          <div className="px-5 py-3.5 border-b border-[#E8EAED] flex items-center justify-between bg-[#F8F9FA]">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-[#1A73E8]" />
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#202124]">
                Live Incident Triage Feed ({incidents.length})
              </h2>
            </div>
            <span className="text-[11px] font-mono text-[#5F6368]">Streaming live from PostgreSQL</span>
          </div>

          <div className="divide-y divide-[#E8EAED]">
            {incidents.length === 0 ? (
              <div className="p-8 text-center text-[#80868B] font-mono text-xs">
                No active incidents found. Dispatch a simulation above to start.
              </div>
            ) : (
              incidents.map((inc) => (
                <Link
                  key={inc.id}
                  href={`/incidents/${inc.id}`}
                  className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-[#F8F9FA] transition-colors group block"
                >
                  <div className="space-y-1 max-w-3xl">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                          inc.severity === "CRITICAL"
                            ? "bg-[#FCE8E6] text-[#C5221F] border border-[#FAD2CF]"
                            : inc.severity === "HIGH"
                            ? "bg-[#FEF7E0] text-[#B06000] border border-[#FEEFC3]"
                            : "bg-[#E8F0FE] text-[#1A73E8] border border-[#D2E3FC]"
                        }`}
                      >
                        {inc.severity}
                      </span>
                      <span className="font-mono font-bold text-sm text-[#202124] group-hover:text-[#1A73E8] transition-colors">
                        {inc.title}
                      </span>
                    </div>

                    <p className="text-xs text-[#5F6368] font-mono line-clamp-1">{inc.description}</p>

                    <div className="flex items-center space-x-3 text-[11px] font-mono text-[#80868B] pt-1">
                      <span>PROJECT: {inc.project || "VFX"}</span>
                      <span>•</span>
                      <span>SHOT: {inc.shot || "SH001"}</span>
                      <span>•</span>
                      <span>SOURCE: {inc.source_system}</span>
                      <span>•</span>
                      <span>TIME: {new Date(inc.created_at).toLocaleTimeString()}</span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3 self-end md:self-center">
                    <span
                      className={`text-[10px] font-mono px-2.5 py-1 rounded font-bold uppercase ${
                        inc.status === "RESOLVED"
                          ? "bg-[#E6F4EA] text-[#137333] border border-[#CEEAD6]"
                          : inc.status === "AWAITING_APPROVAL"
                          ? "bg-[#FEF7E0] text-[#B06000] border border-[#FEEFC3] animate-pulse"
                          : "bg-[#F1F3F4] text-[#5F6368] border border-[#DADCE0]"
                      }`}
                    >
                      {inc.status}
                    </span>
                    <ArrowRight className="w-4 h-4 text-[#BDC1C6] group-hover:text-[#1A73E8] group-hover:translate-x-0.5 transition-all" />
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Compute Blades Grid */}
        <div className="bg-white border border-[#DADCE0] rounded-lg p-5 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-[#E8EAED] pb-3">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#202124] flex items-center space-x-2">
              <Cpu className="w-4 h-4 text-[#1A73E8]" />
              <span>Compute Blade Telemetry (Host + Farm Nodes)</span>
            </h2>
            <span className="text-[11px] font-mono text-[#5F6368]">Live IPMI / psutil telemetry</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {nodes.map((node) => (
              <div key={node.node_id} className="bg-[#F8F9FA] border border-[#DADCE0] rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-[#202124] text-xs truncate max-w-[110px]" title={node.node_id}>
                    {node.node_id}
                  </span>
                  <span
                    className={`text-[9px] font-mono px-1.5 py-0.2 rounded border ${
                      node.status === "ONLINE"
                        ? "bg-[#E6F4EA] text-[#137333] border-[#CEEAD6]"
                        : "bg-[#FCE8E6] text-[#C5221F] border-[#FAD2CF]"
                    }`}
                  >
                    {node.status}
                  </span>
                </div>
                <div className="space-y-1 font-mono text-[11px] text-[#5F6368]">
                  <div className="flex justify-between">
                    <span>CPU LOAD:</span>
                    <span className="text-[#202124] font-medium">{Math.round(node.cpu_utilization)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>GPU VRAM:</span>
                    <span className="text-[#202124] font-medium">{node.gpu_memory_used_percent}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>DISK FREE:</span>
                    <span className="text-[#202124] font-medium">{Math.round(node.scratch_disk_free_gb)} GB</span>
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
