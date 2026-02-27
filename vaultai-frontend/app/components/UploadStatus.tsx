export function UploadStatus({
  filename,
  status,
  progress,
  error,
}: {
  filename: string;
  status: "uploading" | "processing" | "succeeded" | "failed";
  progress?: number;
  error?: string;
}) {
  const colors = {
    uploading:  { bar: "#6366F1", icon: "⏳", text: "Uploading..." },
    processing: { bar: "#8B5CF6", icon: "⚙", text: "Processing document..." },
    succeeded:  { bar: "#22C55E", icon: "✓", text: "Upload complete" },
    failed:     { bar: "#EF4444", icon: "✕", text: error || "Upload failed" },
  };
  const c = colors[status];

  return (
    <div
      style={{
        background: "#1A1D27",
        border: "1px solid #2E3248",
        borderRadius: 10,
        padding: 16,
        marginBottom: 16,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: "#22263A",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            color:
              status === "succeeded"
                ? "#22C55E"
                : status === "failed"
                ? "#EF4444"
                : "#6366F1",
            flexShrink: 0,
          }}
        >
          {c.icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <p
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: "#F1F5F9",
              margin: "0 0 2px",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {filename}
          </p>
          <p style={{ fontSize: 12, color: "#94A3B8", margin: 0 }}>{c.text}</p>

          {(status === "uploading" || status === "processing") && (
            <div
              style={{
                marginTop: 8,
                height: 4,
                background: "#22263A",
                borderRadius: 99,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${progress ?? 50}%`,
                  background: c.bar,
                  borderRadius: 99,
                  transition: "width 0.3s ease",
                }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}