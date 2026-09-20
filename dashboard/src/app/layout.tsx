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
    <html lang="en">
      <body className="bg-[#F8F9FA] text-[#202124] min-h-screen flex flex-col antialiased selection:bg-[#E8F0FE] selection:text-[#1A73E8]">
        {children}
      </body>
    </html>
  );
}
