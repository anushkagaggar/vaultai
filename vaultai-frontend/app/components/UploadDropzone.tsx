"use client";
import { useRef, useState } from "react";

export function UploadDropzone({
  onUpload,
  uploading,
  error,
}: {
  onUpload: (file: File) => void;
  uploading: boolean;
  error: string | null;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onUpload(file);
  };

  return (
    <div>
      <div
        onClick={() => !uploading && fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        style={{
          border: dragOver
            ? "2px solid #6366F1"
            : "2px dashed #2E3248",
          borderRadius: 12,
          padding: "40px 20px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 10,
          cursor: uploading ? "not-allowed" : "pointer",
          background: dragOver ? "rgba(99,102,241,0.05)" : "#1A1D27",
          transition: "all 0.15s ease",
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            background: "#22263A",
            borderRadius: 12,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 22,
            color: "#475569",
          }}
        >
          {uploading ? "⏳" : "⬆"}
        </div>
        <p style={{ fontSize: 14, fontWeight: 500, color: "#94A3B8", margin: 0 }}>
          {uploading ? "Uploading..." : "Drag & drop or click to upload"}
        </p>
        <p style={{ fontSize: 12, color: "#475569", margin: 0 }}>
          Supports PDF and TXT files
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onUpload(file);
          }}
          style={{ display: "none" }}
        />
      </div>

      {error && (
        <div
          style={{
            marginTop: 12,
            padding: "10px 14px",
            background: "rgba(239,68,68,0.08)",
            border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 8,
            fontSize: 13,
            color: "#EF4444",
          }}
        >
          ⚠ {error}
        </div>
      )}
    </div>
  );
}