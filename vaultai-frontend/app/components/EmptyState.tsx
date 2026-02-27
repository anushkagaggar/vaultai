export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void; loading?: boolean };
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "60px 20px",
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          background: "#22263A",
          border: "1px solid #2E3248",
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 20,
          fontSize: 24,
          color: "#475569",
        }}
      >
        ◎
      </div>
      <h3
        style={{
          fontSize: 16,
          fontWeight: 600,
          color: "#F1F5F9",
          margin: "0 0 8px",
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontSize: 14,
          color: "#94A3B8",
          margin: "0 0 24px",
          maxWidth: 340,
          lineHeight: 1.6,
        }}
      >
        {description}
      </p>
      {action && (
        <button
          onClick={action.onClick}
          disabled={action.loading}
          style={{
            padding: "9px 20px",
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 500,
            color: "white",
            background: "#6366F1",
            border: "none",
            cursor: action.loading ? "not-allowed" : "pointer",
            opacity: action.loading ? 0.6 : 1,
          }}
        >
          {action.loading ? "Loading..." : action.label}
        </button>
      )}
    </div>
  );
}