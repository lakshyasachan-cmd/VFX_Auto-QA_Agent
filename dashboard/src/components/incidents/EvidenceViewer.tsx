"use client";

import React, { useState } from "react";
import { IncidentEvidenceItem } from "@/lib/types";
import { Terminal, HardDrive, Layers, FileText, CheckCircle2 } from "lucide-react";

interface Props {
  evidence: IncidentEvidenceItem[];
}

export default function EvidenceViewer({ evidence }: Props) {
  const [activeTab, setActiveTab] = useState<number>(0);

  if (!evidence || evidence.length === 0) {
    return (
      <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-6 text-center text-slate-500 font-mono text-xs">
        No telemetry or evidence artifacts attached to this incident.
      </div>
    );
  }

  const selected = evidence[activeTab] || evidence[0];

  const getIcon = (type: string) => {
    switch (type) {
      case "NODE_TELEMETRY":
        return HardDrive;
      case "RENDER_LOG":
        return Terminal;
      case "USD_DEPENDENCY":
        return Layers;
      default:
        return FileText;
    }
  };

  return (
    <div className="bg-[#0f172a] border border-slate-800 rounded-lg overflow-hidden flex flex-col h-full">
      <div className="border-b border-slate-800 px-4 py-3 bg-slate-900/50 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
            Captured Telemetry & Evidence Artifacts ({evidence.length})
          </span>
        </div>
        <span className="text-[10px] font-mono text-slate-400">Read-Only Ground Truth</span>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 bg-[#0b1120] overflow-x-auto">
        {evidence.map((ev, idx) => {
          const Icon = getIcon(ev.evidence_type);
          const isSelected = idx === activeTab;
          return (
            <button
              key={ev.id}
              onClick={() => setActiveTab(idx)}
              className={`px-4 py-2.5 text-xs font-mono text-left flex items-center space-x-2 border-r border-slate-800 transition-colors whitespace-nowrap ${
                isSelected
                  ? "bg-[#0f172a] text-cyan-400 border-b-2 border-b-cyan-400 font-semibold"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/50"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{ev.title}</span>
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="p-4 space-y-4 flex-1 overflow-y-auto">
        {/* Structured Data Metric Grid */}
        {selected.structured_data && Object.keys(selected.structured_data).length > 0 && (
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-2 font-semibold">
              Parsed Telemetry Metrics
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.entries(selected.structured_data).map(([key, val]) => (
                <div key={key} className="bg-slate-900/80 border border-slate-800/80 rounded p-2 text-xs">
                  <div className="text-[10px] text-slate-500 font-mono uppercase truncate">{key.replace(/_/g, " ")}</div>
                  <div className="font-mono font-semibold text-slate-200 mt-0.5 truncate">
                    {typeof val === "object" ? JSON.stringify(val) : String(val)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Raw Log Output */}
        {selected.raw_content && (
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-2 font-semibold flex items-center justify-between">
              <span>Raw Machine Capture</span>
              <span className="text-[10px] text-slate-500">{selected.captured_at}</span>
            </div>
            <pre className="bg-[#070a12] border border-slate-800 rounded p-3 text-xs font-mono text-rose-300/90 whitespace-pre-wrap overflow-x-auto leading-relaxed">
              {selected.raw_content}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
