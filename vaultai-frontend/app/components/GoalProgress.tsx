import type { FeasibilityLabel } from "../../lib/types/plans";

const LABEL_COLOR: Record<FeasibilityLabel, string> = {
  FEASIBLE:   "#22C55E",
  STRETCH:    "#F59E0B",
  INFEASIBLE: "#EF4444",
};

function fmt(n: number) {
  if (n >= 100000) return `₹${(n / 100000).toFixed(2)}L`;
  if (n >= 1000)   return `₹${(n / 1000).toFixed(1)}K`;
  return `₹${n}`;
}

export default function GoalProgress({
  targetAmount,
  projectedBalance,
  coverageRatio,
  feasibilityLabel,
  gapAmount,
  monthsToGoal,
}: {
  targetAmount: number;
  projectedBalance: number;
  coverageRatio: number;
  feasibilityLabel: FeasibilityLabel;
  gapAmount?: number;
  monthsToGoal?: number | null;
}) {
  const color = LABEL_COLOR[feasibilityLabel];
  const pct = Math.min(100, Math.round(coverageRatio * 100));

  return (
    <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <p style={{ fontSize: 11, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 4px" }}>Goal Progress</p>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 22, fontWeight: 800, color, fontFamily: "monospace" }}>{pct}%</span>
            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 99, background: `${color}18`, color, border: `1px solid ${color}30`, fontWeight: 700 }}>
              {feasibilityLabel}
            </span>
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <p style={{ fontSize: 11, color: "#475569", margin: "0 0 2px" }}>Projected vs Target</p>
          <p style={{ fontSize: 13, fontWeight: 600, color: "#F1F5F9", margin: 0, fontFamily: "monospace" }}>
            {fmt(projectedBalance)} / {fmt(targetAmount)}
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ height: 8, background: "#22263A", borderRadius: 99, overflow: "hidden", marginBottom: 14 }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 99, transition: "width 0.8s ease" }} />
      </div>

      {/* Detail */}
      <div style={{ display: "flex", gap: 16 }}>
        {monthsToGoal != null ? (
          <div style={{ padding: "8px 14px", background: `${color}10`, border: `1px solid ${color}25`, borderRadius: 8 }}>
            <p style={{ fontSize: 11, color: "#475569", margin: "0 0 2px" }}>Months to Goal</p>
            <p style={{ fontSize: 14, fontWeight: 700, color, margin: 0, fontFamily: "monospace" }}>{monthsToGoal} mo</p>
          </div>
        ) : gapAmount && gapAmount > 0 ? (
          <div style={{ padding: "8px 14px", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: 8 }}>
            <p style={{ fontSize: 11, color: "#475569", margin: "0 0 2px" }}>Gap</p>
            <p style={{ fontSize: 14, fontWeight: 700, color: "#EF4444", margin: 0, fontFamily: "monospace" }}>-{fmt(gapAmount)}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}