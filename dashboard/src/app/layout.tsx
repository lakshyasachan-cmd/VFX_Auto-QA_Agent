import "./globals.css";
import React from "react";

export const metadata = {
  title: "VFX Mission Control — Studio Pipeline Incident Platform",
  description: "AI-governed real-time investigation and remediation platform for VFX production farms.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#070b12] text-slate-100 min-h-screen flex flex-col antialiased selection:bg-cyan-500 selection:text-black">
        {children}
      </body>
    </html>
  );
}
