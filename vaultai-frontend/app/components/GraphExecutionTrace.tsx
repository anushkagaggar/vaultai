"use client";
import { useState } from "react";
import type { GraphNode, ValidationStatus } from "../../lib/types/plans";

const NODE_COLORS: Record<string, string> = {
  validation: "#F59E0B",
  llm:        "#6366F1",
  simulation: "#22C55E",
  persist:    "#64748B",
};

export default function GraphExecutionTrace({
  nodes,
  validationStatus,
}: {
  nodes: GraphNode[];
  validationStatus: ValidationStatus;
}) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState<number | null>(null);

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
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#F1F5F9" }}>Graph Execution Trace</span>
          {validationStatus === "fallback" && (
            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 99, background: "rgba(245,158,11,0.12)", color: "#F59E0B", border: "1px solid rgba(245,158,11,0.2)", fontWeight: 600 }}>
              Fallback
            </span>
          )}
        </div>
        <span style={{ fontSize: 12, color: "#475569", transform: open ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>
          ▾
        </span>
      </button>

      {open && (
        <div style={{ padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 0, flexWrap: "wrap" }}>
            {nodes.map((node, i) => {
              const color = NODE_COLORS[node.type] ?? "#64748B";
              return (
                <div key={node.name} style={{ display: "flex", alignItems: "center" }}>
                  <div style={{ position: "relative" }}>
                    <div
                      onMouseEnter={() => setHovered(i)}
                      onMouseLeave={() => setHovered(null)}
                      style={{
                        padding: "5px 12px",
                        borderRadius: 99,
                        fontSize: 11,
                        fontWeight: 600,
                        background: `${color}18`,
                        color,
                        border: `1px solid ${color}40`,
                        cursor: "default",
                        whiteSpace: "nowrap",
                        opacity: node.status === "failed" ? 0.5 : 1,
                      }}
                    >
                      {node.name}
                    </div>
                    {hovered === i && (
                      <div
                        style={{
                          position: "absolute",
                          bottom: "calc(100% + 8px)",
                          left: "50%",
                          transform: "translateX(-50%)",
                          background: "#22263A",
                          border: "1px solid #2E3248",
                          borderRadius: 8,
                          padding: "8px 12px",
                          fontSize: 11,
                          color: "#94A3B8",
                          whiteSpace: "nowrap",
                          zIndex: 10,
                          minWidth: 160,
                        }}
                      >
                        <p style={{ margin: "0 0 2px", fontWeight: 600, color: "#F1F5F9" }}>{node.name}</p>
                        <p style={{ margin: 0 }}>{node.description}</p>
                        <p style={{ margin: "4px 0 0", color: node.status === "success" ? "#22C55E" : "#EF4444" }}>
                          {node.status}
                        </p>
                      </div>
                    )}
                  </div>
                  {i < nodes.length - 1 && (
                    <span style={{ color: "#2E3248", margin: "0 4px", fontSize: 12 }}>→</span>
                  )}
                </div>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 16, flexWrap: "wrap" }}>
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <div key={type} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
                <span style={{ fontSize: 11, color: "#475569", textTransform: "capitalize" }}>{type}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}