export function ExplanationBlock({
  summary,
  degraded,
}: {
  summary: string | null;
  degraded: boolean;
}) {
  if (degraded || !summary) {
    return (
      <div
        style={{
          background: "rgba(245,158,11,0.08)",
          border: "1px solid rgba(245,158,11,0.2)",
          borderLeft: "3px solid #F59E0B",
          borderRadius: 10,
          padding: "14px 16px",
        }}
      >
        <p style={{ fontSize: 12, fontWeight: 600, color: "#F59E0B", marginBottom: 4, margin: "0 0 4px" }}>
          ⚠ AI Explanation Unavailable
        </p>
        <p style={{ fontSize: 13, color: "#94A3B8", margin: 0, lineHeight: 1.6 }}>
          The AI explanation failed validation. Metrics below are accurate and sourced
          directly from your expense data.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        background: "#1A1D27",
        border: "1px solid #2E3248",
        borderLeft: "3px solid #6366F1",
        borderRadius: 10,
        padding: "14px 16px",
      }}
    >
      <p style={{ fontSize: 14, color: "#94A3B8", margin: 0, lineHeight: 1.7 }}>
        {summary}
      </p>
    </div>
  );
}