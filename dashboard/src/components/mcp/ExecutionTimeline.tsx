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
      <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5 text-center text-slate-500 font-mono text-xs">
        No MCP workflow actions have been executed yet. Awaiting governance approval.
      </div>
    );
  }

  return (
    <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5 space-y-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2">
          <Terminal className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
            MCP Tool & watsonx Execution Audit Trail ({executions.length})
          </span>
        </div>
        <span className="text-[10px] font-mono text-slate-400">Cryptographically Verified</span>
      </div>

      <div className="space-y-2">
        {executions.map((item) => (
          <div
            key={item.id}
            className="bg-slate-900 border border-slate-800/80 rounded p-3 text-xs flex flex-col md:flex-row md:items-center justify-between gap-2"
          >
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span className="font-mono font-bold text-white">{item.tool_name}</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-300">
                  ACTOR: {item.actor}
                </span>
              </div>
              <div className="text-[10px] font-mono text-slate-400">
                PARAMS: {JSON.stringify(item.parameters)}
              </div>
            </div>
            <div className="text-right text-[10px] font-mono text-slate-500">
              {item.executed_at}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
