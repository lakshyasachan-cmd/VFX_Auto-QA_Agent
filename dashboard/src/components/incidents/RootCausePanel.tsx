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
      <div className="bg-white border border-[#DADCE0] rounded-lg p-6 text-center text-[#80868B] font-mono text-xs shadow-sm">
        Gemini root cause diagnostic reasoning is currently executing...
      </div>
    );
  }

  const confidencePercent = Math.round(reasoning.confidence * 100);

  return (
    <div className="bg-white border border-[#DADCE0] rounded-lg p-5 flex flex-col space-y-4 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E8EAED] pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#E8F0FE] border border-[#D2E3FC] flex items-center justify-center text-[#1A73E8]">
            <Brain className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold tracking-wider text-[#202124] uppercase">
              Root Cause Diagnostic Analysis (Gemini ADK)
            </h3>
            <p className="text-[11px] text-[#5F6368] font-mono">Synthesized Specialist Findings & Ground Truth</p>
          </div>
        </div>

        {/* Confidence Meter */}
        <div className="flex items-center space-x-2 bg-[#E6F4EA] border border-[#CEEAD6] px-3 py-1.5 rounded-lg">
          <span className="text-[11px] text-[#137333] font-mono uppercase">Confidence</span>
          <span className="text-sm font-mono font-bold text-[#137333]">{confidencePercent}%</span>
        </div>
      </div>

      {/* Primary Root Cause Badge */}
      <div className="bg-[#FCE8E6] border border-[#FAD2CF] rounded-lg p-3.5">
        <div className="text-[10px] font-mono uppercase tracking-wider text-[#C5221F] font-semibold mb-1">
          Identified Root Cause
        </div>
        <div className="text-sm font-mono font-bold text-[#991B1B] leading-snug">
          {reasoning.root_cause.replace(/_/g, " ")}
        </div>
        <p className="text-xs text-[#5F6368] mt-2 leading-relaxed">
          {reasoning.summary}
        </p>
      </div>

      {/* Supporting vs Contradicting Evidence */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Supporting */}
        <div className="bg-[#F8F9FA] border border-[#DADCE0] rounded-lg p-3 text-xs space-y-2">
          <div className="text-[10px] font-mono uppercase tracking-wider text-[#137333] font-semibold flex items-center space-x-1.5">
            <CheckCircle className="w-3.5 h-3.5 text-[#188038]" />
            <span>Supporting Observed Evidence</span>
          </div>
          <ul className="space-y-1.5">
            {reasoning.supporting_evidence.map((ev, i) => (
              <li key={i} className="text-[#3C4043] font-mono text-[11px] flex items-start space-x-2">
                <span className="text-[#188038] font-bold">•</span>
                <span>{ev}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Contradicting or Alternative */}
        <div className="bg-[#F8F9FA] border border-[#DADCE0] rounded-lg p-3 text-xs space-y-2">
          <div className="text-[10px] font-mono uppercase tracking-wider text-[#5F6368] font-semibold flex items-center space-x-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-[#80868B]" />
            <span>Alternative Hypotheses Evaluated</span>
          </div>
          <ul className="space-y-1.5">
            {reasoning.alternative_causes.map((alt, i) => (
              <li key={i} className="text-[#5F6368] font-mono text-[11px] flex items-center justify-between">
                <span>{alt.cause}</span>
                <span className="text-[#80868B]">{Math.round(alt.probability * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
