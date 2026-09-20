"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Shield, Cpu, Clock } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
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

  // Determine active tab
  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const tabClass = (href: string) =>
    isActive(href)
      ? "px-3 py-1.5 rounded-md text-[#1A73E8] font-semibold bg-[#E8F0FE] border border-[#D2E3FC] transition-colors text-xs font-medium"
      : "px-3 py-1.5 rounded-md hover:bg-[#F1F3F4] text-[#5F6368] hover:text-[#202124] transition-colors text-xs font-medium";

  return (
    <header className="border-b border-[#DADCE0] bg-white/95 backdrop-blur sticky top-0 z-50 px-6 py-3 flex items-center justify-between shadow-[0_1px_2px_0_rgba(60,64,67,0.06)]">
      <div className="flex items-center space-x-6">
        <Link href="/" className="flex items-center space-x-3 group">
          <div className="w-8 h-8 rounded-lg bg-[#E8F0FE] border border-[#D2E3FC] flex items-center justify-center text-[#1A73E8] group-hover:border-[#1A73E8] transition-colors">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-sm tracking-wider uppercase flex items-center space-x-2">
              <span className="text-[#202124]">VFX MISSION CONTROL</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#E8F0FE] text-[#1A73E8] border border-[#D2E3FC] font-mono">v1.0-LIVE</span>
            </div>
            <div className="text-[11px] text-[#5F6368] font-mono">Studio Pipeline Incident Platform</div>
          </div>
        </Link>

        <nav className="hidden md:flex items-center space-x-1 pl-6 border-l border-[#DADCE0]">
          <Link href="/" className={tabClass("/")}>
            Overview
          </Link>
          <Link href="/approvals" className={`${tabClass("/approvals")} flex items-center space-x-1.5`}>
            <Shield className="w-3.5 h-3.5 text-[#F9AB00]" />
            <span>Governance Queue</span>
          </Link>
          <Link href="/analytics" className={`${tabClass("/analytics")} flex items-center space-x-1.5`}>
            <Cpu className="w-3.5 h-3.5 text-[#5F6368]" />
            <span>Cluster Health</span>
          </Link>
        </nav>
      </div>

      <div className="flex items-center space-x-4 text-xs font-mono">
        <div className="hidden lg:flex items-center space-x-2 px-2.5 py-1 rounded bg-[#F8F9FA] border border-[#DADCE0] text-[#3C4043]">
          <span className="w-2 h-2 rounded-full bg-[#188038] animate-pulse"></span>
          <span>GEMINI ADK FLEET: ONLINE</span>
        </div>
        <div className="flex items-center space-x-1 text-[#5F6368]">
          <Clock className="w-3.5 h-3.5 text-[#80868B]" />
          <span>{time || "SYNCING..."}</span>
        </div>
      </div>
    </header>
  );
}
