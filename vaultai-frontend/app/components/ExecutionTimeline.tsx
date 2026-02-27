export function ExecutionTimeline({
  status,
  executionId,
}: {
  status: string;
  executionId: number | null;
}) {
  const stages = [
    { key: "analytics",   label: "Analytics Engine" },
    { key: "llm",         label: "LLM Explanation" },
    { key: "rag",         label: "RAG Retrieval" },
    { key: "validation",  label: "Validation" },
    { key: "confidence",  label: "Confidence Score" },
  ];

  const currentIndex = status === "pending" ? 0 : status === "running" ? 2 : 4;

  return (
    <div
      style={{
        background: "#1A1D27",
        border: "1px solid #2E3248",
        borderRadius: 12,
        padding: 20,
        marginBottom: 20,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <span
          style={{
            width: 16,
            height: 16,
            border: "2px solid #6366F1",
            borderTop: "2px solid transparent",
            borderRadius: "50%",
            display: "inline-block",
            animation: "spin 0.8s linear infinite",
          }}
        />
        <p style={{ fontSize: 13, fontWeight: 500, color: "#F1F5F9", margin: 0 }}>
          Computing insight...
        </p>
        {executionId && (
          <span
            style={{
              fontSize: 11,
              color: "#475569",
              fontFamily: "'JetBrains Mono', monospace",
              marginLeft: "auto",
            }}
          >
            #{executionId}
          </span>
        )}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        {stages.map((stage, i) => {
          const done = i < currentIndex;
          const active = i === currentIndex;
          return (
            <div key={stage.key} style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              {/* Left column: dot + line */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 20 }}>
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    background: done
                      ? "#22C55E"
                      : active
                      ? "#6366F1"
                      : "#22263A",
                    border: active
                      ? "2px solid #6366F1"
                      : done
                      ? "none"
                      : "2px solid #2E3248",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 10,
                    color: "white",
                    flexShrink: 0,
                    boxShadow: active ? "0 0 0 4px rgba(99,102,241,0.15)" : "none",
                  }}
                >
                  {done ? "✓" : active ? "•" : ""}
                </div>
                {i < stages.length - 1 && (
                  <div
                    style={{
                      width: 1,
                      height: 20,
                      background: done ? "#22C55E" : "#2E3248",
                    }}
                  />
                )}
              </div>
              {/* Label */}
              <p
                style={{
                  fontSize: 13,
                  color: done ? "#22C55E" : active ? "#F1F5F9" : "#475569",
                  margin: "1px 0 19px",
                  fontWeight: active ? 500 : 400,
                }}
              >
                {stage.label}
              </p>
            </div>
          );
        })}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}