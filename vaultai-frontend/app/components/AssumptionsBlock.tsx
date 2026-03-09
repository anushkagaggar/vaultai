"use client";
import { useState } from "react";

interface AssumptionsBlockProps {
  assumptions: Record<string, unknown>;
  constraints?: Record<string, unknown>;
}

function formatValue(key: string, value: unknown): string {
  if (typeof value === "number") {
    if (key.includes("rate") || key.includes("ratio") || key.includes("percent")) {
      return value < 1 ? `${(value * 100).toFixed(1)}%` : `${value.toFixed(1)}%`;
    }
    if (value > 1000) {
      if (value >= 10000000) return `₹${(value / 10000000).toFixed(2)}Cr`;
      if (value >= 100000) return `₹${(value / 100000).toFixed(2)}L`;
      if (value >= 1000) return `₹${(value / 1000).toFixed(1)}K`;
    }
    return String(value);
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value ?? "—");
}

function formatKey(key: string): string {
  return key.replace(/constraint_/g, "").replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

export default function AssumptionsBlock({ assumptions, constraints }: AssumptionsBlockProps) {
  const [open, setOpen] = useState(false);

  const all: Record<string, unknown> = {
    ...assumptions,
    ...(constraints ? Object.fromEntries(Object.entries(constraints).map(([k, v]) => [`constraint_${k}`, v])) : {}),
  };

  const entries = Object.entries(all);

  return (
    <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, overflow: "hidden" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 20px",
          background: "none",
          border: "none",
          cursor: "pointer",
          borderBottom: open ? "1px solid #2E3248" : "none",
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 600, color: "#F1F5F9" }}>
          Assumptions & Constraints
        </span>
        <span style={{ fontSize: 12, color: "#475569", transform: open ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>
          ▾
        </span>
      </button>

      {open && (
        <div style={{ padding: 20 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 24px" }}>
            {entries.map(([key, value]) => (
              <div
                key={key}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "8px 0",
                  borderBottom: "1px solid #2E3248",
                }}
              >
                <span style={{ fontSize: 12, color: "#94A3B8" }}>{formatKey(key)}</span>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: key.startsWith("constraint_") ? "#F59E0B" : "#F1F5F9",
                    fontFamily: "monospace",
                  }}
                >
                  {formatValue(key, value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}