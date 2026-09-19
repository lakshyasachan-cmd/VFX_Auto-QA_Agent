"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, Shield, Cpu, Clock, Terminal } from "lucide-react";

export default function Navbar() {
  const [time, setTime] = useState("");

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(now.toISOString().replace("T", " ").substring(0, 19) + " UTC");
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="border-b border-slate-800 bg-[#0b1120]/90 backdrop-blur sticky top-0 z-50 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center space-x-6">
        <Link href="/" className="flex items-center space-x-3 group">
          <div className="w-8 h-8 rounded bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 group-hover:border-cyan-400 transition-colors">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-sm tracking-wider uppercase flex items-center space-x-2">
              <span className="text-white">VFX MISSION CONTROL</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono">v1.0-LIVE</span>
            </div>
            <div className="text-[11px] text-slate-400 font-mono">Studio Pipeline Incident Platform</div>
          </div>
        </Link>

        <nav className="hidden md:flex items-center space-x-1 pl-6 border-l border-slate-800 text-xs font-medium">
          <Link href="/" className="px-3 py-1.5 rounded-md hover:bg-slate-800/60 text-slate-300 hover:text-white transition-colors">
            Overview
          </Link>
          <Link href="/incidents/inc-1042-oom" className="px-3 py-1.5 rounded-md hover:bg-slate-800/60 text-cyan-400 font-semibold bg-cyan-500/10 border border-cyan-500/20">
            Active Incident Trace
          </Link>
          <Link href="/approvals" className="px-3 py-1.5 rounded-md hover:bg-slate-800/60 text-slate-300 hover:text-white transition-colors flex items-center space-x-1.5">
            <Shield className="w-3.5 h-3.5 text-amber-400" />
            <span>Governance Queue</span>
            <span className="px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-mono">1</span>
          </Link>
          <Link href="/analytics" className="px-3 py-1.5 rounded-md hover:bg-slate-800/60 text-slate-300 hover:text-white transition-colors flex items-center space-x-1.5">
            <Cpu className="w-3.5 h-3.5 text-slate-400" />
            <span>Cluster Health</span>
          </Link>
        </nav>
      </div>

      <div className="flex items-center space-x-4 text-xs font-mono">
        <div className="hidden lg:flex items-center space-x-2 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>GEMINI ADK FLEET: ONLINE</span>
        </div>
        <div className="flex items-center space-x-1 text-slate-400">
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span>{time || "SYNCING..."}</span>
        </div>
      </div>
    </header>
  );
}
