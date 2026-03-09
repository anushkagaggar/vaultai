"use client";
import { useState } from "react";

export interface SimulationParams {
  incomeMonthly: number;
  monthlySavings: number;
  targetAmount: number;
  horizonMonths: number;
  annualRate: number;
  scenarioLabel: string;
}

const inputStyle = {
  width: "100%",
  padding: "9px 12px",
  borderRadius: 8,
  border: "1px solid #2E3248",
  background: "#22263A",
  color: "#F1F5F9",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box" as const,
};

export default function SimulateForm({
  onSimulate,
  isLoading,
}: {
  onSimulate: (params: SimulationParams) => void;
  isLoading: boolean;
}) {
  const [params, setParams] = useState<SimulationParams>({
    incomeMonthly: 80000,
    monthlySavings: 20000,
    targetAmount: 500000,
    horizonMonths: 24,
    annualRate: 8,
    scenarioLabel: "Scenario 1",
  });

  const set = (key: keyof SimulationParams) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = key === "scenarioLabel" ? e.target.value : Number(e.target.value);
    setParams((p) => ({ ...p, [key]: val }));
  };

  const fields: { label: string; key: keyof SimulationParams; prefix?: string; type?: string; min?: number; max?: number; step?: number }[] = [
    { label: "Monthly Income", key: "incomeMonthly", prefix: "₹" },
    { label: "Monthly Savings", key: "monthlySavings", prefix: "₹" },
    { label: "Target Amount", key: "targetAmount", prefix: "₹" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {fields.map(({ label, key, prefix }) => (
        <div key={key}>
          <label style={{ display: "block", fontSize: 12, color: "#94A3B8", marginBottom: 6 }}>{label}</label>
          <div style={{ position: "relative" }}>
            {prefix && <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "#475569", fontSize: 14 }}>{prefix}</span>}
            <input
              type="number"
              value={params[key] as number}
              onChange={set(key)}
              style={{ ...inputStyle, paddingLeft: prefix ? 24 : 12 }}
            />
          </div>
        </div>
      ))}

      {/* Horizon slider */}
      <div>
        <label style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#94A3B8", marginBottom: 6 }}>
          <span>Horizon</span>
          <span style={{ color: "#F1F5F9", fontWeight: 600 }}>{params.horizonMonths} months</span>
        </label>
        <input
          type="range"
          min={1} max={120} step={1}
          value={params.horizonMonths}
          onChange={set("horizonMonths")}
          style={{ width: "100%", accentColor: "#6366F1" }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#475569", marginTop: 2 }}>
          <span>1 mo</span><span>120 mo</span>
        </div>
      </div>

      {/* Annual rate slider */}
      <div>
        <label style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#94A3B8", marginBottom: 6 }}>
          <span>Annual Rate</span>
          <span style={{ color: "#F1F5F9", fontWeight: 600 }}>{params.annualRate}%</span>
        </label>
        <input
          type="range"
          min={0} max={30} step={0.5}
          value={params.annualRate}
          onChange={set("annualRate")}
          style={{ width: "100%", accentColor: "#6366F1" }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#475569", marginTop: 2 }}>
          <span>0%</span><span>30%</span>
        </div>
      </div>

      {/* Label */}
      <div>
        <label style={{ display: "block", fontSize: 12, color: "#94A3B8", marginBottom: 6 }}>Scenario Label</label>
        <input
          type="text"
          value={params.scenarioLabel}
          onChange={(e) => setParams((p) => ({ ...p, scenarioLabel: e.target.value }))}
          style={inputStyle}
        />
      </div>

      <button
        onClick={() => onSimulate(params)}
        disabled={isLoading}
        style={{
          width: "100%",
          padding: "11px",
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 600,
          color: "white",
          background: isLoading ? "#4B5563" : "#6366F1",
          border: "none",
          cursor: isLoading ? "not-allowed" : "pointer",
          marginTop: 4,
        }}
      >
        {isLoading ? "Simulating..." : "Run Simulation"}
      </button>
    </div>
  );
}