"use client";

export function RefreshButton({
  onClick,
  loading,
}: {
  onClick: () => void;
  loading: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 16px",
        borderRadius: 8,
        fontSize: 14,
        fontWeight: 500,
        color: "white",
        background: loading ? "#4B5563" : "#6366F1",
        border: "none",
        cursor: loading ? "not-allowed" : "pointer",
        opacity: loading ? 0.7 : 1,
        transition: "all 0.15s ease",
      }}
      onMouseEnter={(e) => {
        if (!loading)
          (e.currentTarget as HTMLButtonElement).style.background = "#818CF8";
      }}
      onMouseLeave={(e) => {
        if (!loading)
          (e.currentTarget as HTMLButtonElement).style.background = "#6366F1";
      }}
    >
      {loading ? (
        <>
          <span
            style={{
              width: 14,
              height: 14,
              border: "2px solid rgba(255,255,255,0.3)",
              borderTop: "2px solid white",
              borderRadius: "50%",
              display: "inline-block",
              animation: "spin 0.8s linear infinite",
            }}
          />
          Computing...
        </>
      ) : (
        <>
          <span style={{ fontSize: 14 }}>↻</span>
          Refresh Insight
        </>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </button>
  );
}