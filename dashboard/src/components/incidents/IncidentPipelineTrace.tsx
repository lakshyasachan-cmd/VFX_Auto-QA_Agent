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
    <div className="bg-white border border-[#DADCE0] rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-mono font-bold tracking-wider text-[#202124] uppercase flex items-center space-x-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#1A73E8]"></span>
          <span>End-to-End Investigation & Remediation Trace</span>
        </h3>
        <span className="text-[11px] font-mono text-[#1A73E8] bg-[#E8F0FE] px-2 py-0.5 rounded border border-[#D2E3FC]">
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
                      ? "bg-[#FEF7E0] border-[#FEEFC3] text-[#B06000] ring-1 ring-[#F9AB00]/30"
                      : isComplete
                      ? "bg-[#F8F9FA] border-[#DADCE0] text-[#202124]"
                      : "bg-[#F8F9FA]/50 border-[#E8EAED] text-[#80868B]"
                  }`}
                >
                  <div
                    className={`w-6 h-6 rounded flex items-center justify-center text-xs ${
                      isActive
                        ? "bg-[#FEF7E0] text-[#B06000] animate-pulse"
                        : isComplete
                        ? "bg-[#E6F4EA] text-[#188038]"
                        : "bg-[#F1F3F4] text-[#BDC1C6]"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <div className="text-[11px] font-mono font-bold tracking-tight">{step.name}</div>
                    <div className="text-[10px] text-[#5F6368] font-mono">{step.sub}</div>
                  </div>
                </div>

                {!isLast && (
                  <ChevronRight
                    className={`w-4 h-4 flex-shrink-0 ${
                      isComplete ? "text-[#5F6368]" : "text-[#BDC1C6]"
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
