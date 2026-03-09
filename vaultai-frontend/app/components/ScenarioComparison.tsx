import type { ScenarioResult } from "../../lib/types/plans";

function fmt(n: number) {
  if (n >= 100000) return `₹${(n / 100000).toFixed(2)}L`;
  if (n >= 1000)   return `₹${(n / 1000).toFixed(1)}K`;
  return `₹${n}`;
}

export default function ScenarioComparison({ scenarios }: { scenarios: ScenarioResult[] }) {
  if (!scenarios.length) return null;
  const best = scenarios.reduce((a, b) => (a.finalBalance > b.finalBalance ? a : b));

  return (
    <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "14px 20px", borderBottom: "1px solid #2E3248", background: "#0F1117" }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", margin: 0 }}>
          Scenario Comparison
        </p>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #2E3248" }}>
              {["Scenario", "Final Balance", "Contributed", "Growth", "Months to Goal"].map((h) => (
                <th key={h} style={{ padding: "10px 16px", textAlign: h === "Scenario" ? "left" : "right", fontSize: 11, fontWeight: 600, color: "#475569", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s) => {
              const isBest = s.label === best.label;
              return (
                <tr key={s.label} style={{ borderBottom: "1px solid #2E3248", background: isBest ? "rgba(34,197,94,0.04)" : "transparent" }}>
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13, color: "#F1F5F9", fontWeight: 500 }}>{s.label}</span>
                      {isBest && (
                        <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 99, background: "rgba(34,197,94,0.12)", color: "#22C55E", fontWeight: 700, border: "1px solid rgba(34,197,94,0.2)" }}>
                          BEST
                        </span>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right", fontSize: 13, fontWeight: 700, color: isBest ? "#22C55E" : "#6366F1", fontFamily: "monospace" }}>
                    {fmt(s.finalBalance)}
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right", fontSize: 13, color: "#94A3B8", fontFamily: "monospace" }}>
                    {fmt(s.totalContributed)}
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right", fontSize: 13, color: "#22C55E", fontFamily: "monospace" }}>
                    +{fmt(s.totalGrowth)}
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right", fontSize: 13, color: "#F1F5F9", fontFamily: "monospace" }}>
                    {s.monthsToGoal !== null ? `${s.monthsToGoal} mo` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}