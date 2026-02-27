export function StatusBadge({
  degraded,
  confidence,
}: {
  degraded: boolean;
  confidence: number;
}) {
  if (degraded) {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "3px 10px",
          borderRadius: 99,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.05em",
          textTransform: "uppercase" as const,
          background: "rgba(245,158,11,0.12)",
          color: "#F59E0B",
          border: "1px solid rgba(245,158,11,0.2)",
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "#F59E0B",
            display: "inline-block",
          }}
        />
        Degraded
      </span>
    );
  }

  if (confidence < 0.4) {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "3px 10px",
          borderRadius: 99,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.05em",
          textTransform: "uppercase" as const,
          background: "rgba(239,68,68,0.12)",
          color: "#EF4444",
          border: "1px solid rgba(239,68,68,0.2)",
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "#EF4444",
            display: "inline-block",
          }}
        />
        Low Trust
      </span>
    );
  }

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 10px",
        borderRadius: 99,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: "0.05em",
        textTransform: "uppercase" as const,
        background: "rgba(34,197,94,0.12)",
        color: "#22C55E",
        border: "1px solid rgba(34,197,94,0.2)",
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: "#22C55E",
          display: "inline-block",
        }}
      />
      Trusted
    </span>
  );
}