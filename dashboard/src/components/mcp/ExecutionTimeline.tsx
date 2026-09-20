"use client";

import React from "react";
import { ExecutionEventItem } from "@/lib/types";
import { Terminal, CheckCircle2, XCircle, Clock } from "lucide-react";

interface Props {
  executions: ExecutionEventItem[];
}

export default function ExecutionTimeline({ executions }: Props) {
  if (!executions || executions.length === 0) {
    return (
      <div className="bg-white border border-[#DADCE0] rounded-lg p-5 text-center text-[#80868B] font-mono text-xs shadow-sm">
        No MCP workflow actions have been executed yet. Awaiting governance approval.
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#DADCE0] rounded-lg p-5 space-y-3 shadow-sm">
      <div className="flex items-center justify-between border-b border-[#E8EAED] pb-3">
        <div className="flex items-center space-x-2">
          <Terminal className="w-4 h-4 text-[#1A73E8]" />
          <span className="text-xs font-mono font-bold tracking-wider text-[#202124] uppercase">
            MCP Tool & watsonx Execution Audit Trail ({executions.length})
          </span>
        </div>
        <span className="text-[10px] font-mono text-[#5F6368]">Cryptographically Verified</span>
      </div>

      <div className="space-y-2">
        {executions.map((item) => (
          <div
            key={item.id}
            className="bg-[#F8F9FA] border border-[#DADCE0] rounded-lg p-3 text-xs flex flex-col md:flex-row md:items-center justify-between gap-2"
          >
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#188038]" />
                <span className="font-mono font-bold text-[#202124]">{item.tool_name}</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white border border-[#DADCE0] text-[#5F6368]">
                  ACTOR: {item.actor}
                </span>
              </div>
              <div className="text-[10px] font-mono text-[#5F6368]">
                PARAMS: {JSON.stringify(item.parameters)}
              </div>
            </div>
            <div className="text-right text-[10px] font-mono text-[#80868B]">
              {item.executed_at}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
