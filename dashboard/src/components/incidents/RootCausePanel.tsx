"use client";

import React from "react";
import { ReasoningResultItem } from "@/lib/types";
import { Brain, CheckCircle, AlertCircle, HelpCircle } from "lucide-react";

interface Props {
  reasoning?: ReasoningResultItem;
}

export default function RootCausePanel({ reasoning }: Props) {
  if (!reasoning) {
    return (
      <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-6 text-center text-slate-500 font-mono text-xs">
        Gemini root cause diagnostic reasoning is currently executing...
      </div>
    );
  }

  const confidencePercent = Math.round(reasoning.confidence * 100);

  return (
    <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5 flex flex-col space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Brain className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
              Root Cause Diagnostic Analysis (Gemini ADK)
            </h3>
            <p className="text-[11px] text-slate-400 font-mono">Synthesized Specialist Findings & Ground Truth</p>
          </div>
        </div>

        {/* Confidence Meter */}
        <div className="flex items-center space-x-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded">
          <span className="text-[11px] text-slate-400 font-mono uppercase">Confidence</span>
          <span className="text-sm font-mono font-bold text-emerald-400">{confidencePercent}%</span>
        </div>
      </div>

      {/* Primary Root Cause Badge */}
      <div className="bg-rose-950/20 border border-rose-800/40 rounded-md p-3.5">
        <div className="text-[10px] font-mono uppercase tracking-wider text-rose-400 font-semibold mb-1">
          Identified Root Cause
        </div>
        <div className="text-sm font-mono font-bold text-rose-200 leading-snug">
          {reasoning.root_cause.replace(/_/g, " ")}
        </div>
        <p className="text-xs text-slate-300 mt-2 leading-relaxed">
          {reasoning.summary}
        </p>
      </div>

      {/* Supporting vs Contradicting Evidence */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Supporting */}
        <div className="bg-slate-900/60 border border-slate-800 rounded p-3 text-xs space-y-2">
          <div className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-semibold flex items-center space-x-1.5">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Supporting Observed Evidence</span>
          </div>
          <ul className="space-y-1.5">
            {reasoning.supporting_evidence.map((ev, i) => (
              <li key={i} className="text-slate-300 font-mono text-[11px] flex items-start space-x-2">
                <span className="text-emerald-500 font-bold">•</span>
                <span>{ev}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Contradicting or Alternative */}
        <div className="bg-slate-900/60 border border-slate-800 rounded p-3 text-xs space-y-2">
          <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center space-x-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
            <span>Alternative Hypotheses Evaluated</span>
          </div>
          <ul className="space-y-1.5">
            {reasoning.alternative_causes.map((alt, i) => (
              <li key={i} className="text-slate-400 font-mono text-[11px] flex items-center justify-between">
                <span>{alt.cause}</span>
                <span className="text-slate-500">{Math.round(alt.probability * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
