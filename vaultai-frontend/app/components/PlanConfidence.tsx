import type { PlanConfidence as PlanConfidenceType } from "../../lib/types/plans";

const RISK_COLOR: Record<string, string> = {
  low:    "#22C55E",
  medium: "#F59E0B",
  high:   "#EF4444",
};

const FRESH_COLOR: Record<string, string> = {
  live:     "#22C55E",
  cached:   "#F59E0B",
  fallback: "#EF4444",
};

export default function PlanConfidence({ confidence }: { confidence: PlanConfidenceType }) {
  const overall = Math.round(confidence.overall * 100);
  const coverage = Math.round(confidence.dataCoverage * 100);

  return (
    <div
      style={{
        background: "#22263A",
        border: "1px solid #2E3248",
        borderRadius: 10,
        padding: "14px 16px",
        minWidth: 180,
      }}
    >
      <p style={{ fontSize: 10, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.1em", margin: "0 0 10px" }}>
        Plan Confidence
      </p>

      {/* Overall */}
      <p style={{ fontSize: 28, fontWeight: 800, color: overall >= 70 ? "#22C55E" : overall >= 40 ? "#F59E0B" : "#EF4444", margin: "0 0 8px", fontFamily: "monospace" }}>
        {overall}%
      </p>

      {/* Data coverage bar */}
      <p style={{ fontSize: 11, color: "#94A3B8", margin: "0 0 4px" }}>
        Data Coverage: <span style={{ color: "#F1F5F9", fontWeight: 600 }}>{coverage}%</span>
      </p>
      <div style={{ height: 4, background: "#2E3248", borderRadius: 99, marginBottom: 10, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${coverage}%`, background: "#6366F1", borderRadius: 99 }} />
      </div>

      {/* Badges */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 99, background: `${RISK_COLOR[confidence.assumptionRisk]}18`, color: RISK_COLOR[confidence.assumptionRisk], border: `1px solid ${RISK_COLOR[confidence.assumptionRisk]}30`, fontWeight: 600 }}>
          {confidence.assumptionRisk} risk
        </span>
        <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 99, background: `${FRESH_COLOR[confidence.externalFreshness]}18`, color: FRESH_COLOR[confidence.externalFreshness], border: `1px solid ${FRESH_COLOR[confidence.externalFreshness]}30`, fontWeight: 600 }}>
          {confidence.externalFreshness}
        </span>
      </div>
    </div>
  );
}