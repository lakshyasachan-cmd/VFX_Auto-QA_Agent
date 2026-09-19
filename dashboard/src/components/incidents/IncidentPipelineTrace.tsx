"use client";

import React from "react";
import { CheckCircle2, ChevronRight, AlertTriangle, ShieldCheck, Wrench, Brain, Cpu, Database } from "lucide-react";

interface PipelineStep {
  id: string;
  name: string;
  sub: string;
  status: "COMPLETE" | "ACTIVE" | "PENDING" | "FAILED";
  icon: any;
}

export default function IncidentPipelineTrace() {
  const steps: PipelineStep[] = [
    { id: "event", name: "EVENT", sub: "Arnold Abort", status: "COMPLETE", icon: AlertTriangle },
    { id: "supervisor", name: "SUPERVISOR", sub: "ADK Router", status: "COMPLETE", icon: Cpu },
    { id: "specialists", name: "SPECIALISTS", sub: "4 Agents", status: "COMPLETE", icon: Database },
    { id: "evidence", name: "EVIDENCE", sub: "3 Artifacts", status: "COMPLETE", icon: Database },
    { id: "reasoning", name: "GEMINI REASONING", sub: "97% Conf", status: "COMPLETE", icon: Brain },
    { id: "remediation", name: "REMEDIATION", sub: "3 Actions", status: "COMPLETE", icon: Wrench },
    { id: "policy", name: "POLICY", sub: "Deterministic Gate", status: "COMPLETE", icon: ShieldCheck },
    { id: "approval", name: "APPROVAL", sub: "HITL Required", status: "ACTIVE", icon: ShieldCheck },
    { id: "mcp", name: "MCP", sub: "Tool Gateway", status: "PENDING", icon: Cpu },
    { id: "workflow", name: "WORKFLOW", sub: "watsonx / Farm", status: "PENDING", icon: CheckCircle2 },
  ];

  return (
    <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-mono font-bold tracking-wider text-slate-300 uppercase flex items-center space-x-2">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
          <span>End-to-End Investigation & Remediation Trace</span>
        </h3>
        <span className="text-[11px] font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
          STAGE 8: AWAITING HUMAN GOVERNANCE SIGN-OFF
        </span>
      </div>

      <div className="overflow-x-auto pb-1">
        <div className="flex items-center space-x-2 min-w-max">
          {steps.map((step, idx) => {
            const Icon = step.icon;
            const isLast = idx === steps.length - 1;
            const isComplete = step.status === "COMPLETE";
            const isActive = step.status === "ACTIVE";

            return (
              <React.Fragment key={step.id}>
                <div
                  className={`px-3 py-2 rounded-md border text-left flex items-center space-x-2.5 transition-all ${
                    isActive
                      ? "bg-amber-500/10 border-amber-500/50 text-amber-300 ring-1 ring-amber-500/30"
                      : isComplete
                      ? "bg-slate-900 border-slate-700/80 text-slate-200"
                      : "bg-slate-900/40 border-slate-800/60 text-slate-500"
                  }`}
                >
                  <div
                    className={`w-6 h-6 rounded flex items-center justify-center text-xs ${
                      isActive
                        ? "bg-amber-500/20 text-amber-400 animate-pulse"
                        : isComplete
                        ? "bg-emerald-500/20 text-emerald-400"
                        : "bg-slate-800 text-slate-600"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <div className="text-[11px] font-mono font-bold tracking-tight">{step.name}</div>
                    <div className="text-[10px] text-slate-400 font-mono">{step.sub}</div>
                  </div>
                </div>

                {!isLast && (
                  <ChevronRight
                    className={`w-4 h-4 flex-shrink-0 ${
                      isComplete ? "text-slate-600" : "text-slate-800"
                    }`}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
