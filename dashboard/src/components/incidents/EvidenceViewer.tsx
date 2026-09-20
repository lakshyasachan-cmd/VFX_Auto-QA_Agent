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
      <div className="bg-white border border-[#DADCE0] rounded-lg p-6 text-center text-[#80868B] font-mono text-xs shadow-sm">
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
    <div className="bg-white border border-[#DADCE0] rounded-lg overflow-hidden flex flex-col h-full shadow-sm">
      <div className="border-b border-[#E8EAED] px-4 py-3 bg-[#F8F9FA] flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-[#1A73E8]" />
          <span className="text-xs font-mono font-bold tracking-wider text-[#202124] uppercase">
            Captured Telemetry & Evidence Artifacts ({evidence.length})
          </span>
        </div>
        <span className="text-[10px] font-mono text-[#5F6368]">Read-Only Ground Truth</span>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#DADCE0] bg-[#F8F9FA] overflow-x-auto">
        {evidence.map((ev, idx) => {
          const Icon = getIcon(ev.evidence_type);
          const isSelected = idx === activeTab;
          return (
            <button
              key={ev.id}
              onClick={() => setActiveTab(idx)}
              className={`px-4 py-2.5 text-xs font-mono text-left flex items-center space-x-2 border-r border-[#DADCE0] transition-colors whitespace-nowrap ${
                isSelected
                  ? "bg-white text-[#1A73E8] border-b-2 border-b-[#1A73E8] font-semibold"
                  : "text-[#5F6368] hover:text-[#202124] hover:bg-white/60"
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
            <div className="text-[11px] font-mono uppercase tracking-wider text-[#5F6368] mb-2 font-semibold">
              Parsed Telemetry Metrics
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.entries(selected.structured_data).map(([key, val]) => (
                <div key={key} className="bg-[#F8F9FA] border border-[#DADCE0] rounded-lg p-2 text-xs">
                  <div className="text-[10px] text-[#80868B] font-mono uppercase truncate">{key.replace(/_/g, " ")}</div>
                  <div className="font-mono font-semibold text-[#202124] mt-0.5 truncate">
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
            <div className="text-[11px] font-mono uppercase tracking-wider text-[#5F6368] mb-2 font-semibold flex items-center justify-between">
              <span>Raw Machine Capture</span>
              <span className="text-[10px] text-[#80868B]">{selected.captured_at}</span>
            </div>
            <pre className="bg-[#F8F9FA] border border-[#DADCE0] rounded-lg p-3 text-xs font-mono text-[#C5221F] whitespace-pre-wrap overflow-x-auto leading-relaxed">
              {selected.raw_content}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
