"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getRagDocuments, uploadRagDocument, deleteRagDocument } from "../../lib/backend";
import type { RagDocument } from "../../lib/backend";
import { UploadDropzone } from "../components/UploadDropzone";
import { EmptyState } from "../components/EmptyState";
import { UploadStatus } from "../components/UploadStatus";
import AuthenticatedLayout from "../components/Authenticatedlayout";

interface UploadProgress {
  filename: string;
  status: "uploading" | "processing" | "succeeded" | "failed";
  progress: number;
  error?: string;
  docId?: number;
}

export default function UploadsPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<RagDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);

  // ── ALL original logic kept ───────────────────────────────────────
  const fetchDocs = async () => {
    try {
      const data = await getRagDocuments();
      setDocs(data);
      setError(null);
    } catch (error: any) {
      if (error.message === "unauthorized") router.push("/auth");
      else setError("Failed to load documents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDocs(); }, []);

  const handleUpload = async (file: File) => {
    const allowed = ["application/pdf", "text/plain"];
    if (!allowed.includes(file.type)) { setError("Only PDF and TXT files are supported"); return; }
    setUploading(true);
    setError(null);
    setUploadProgress({ filename: file.name, status: "uploading", progress: 0 });
    try {
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (!prev || prev.progress >= 90) return prev;
          return { ...prev, progress: prev.progress + 10 };
        });
      }, 200);
      const result = await uploadRagDocument(file);
      clearInterval(progressInterval);
      setUploadProgress({ filename: file.name, status: "processing", progress: 95, docId: result.id });
      await new Promise((r) => setTimeout(r, 1000));
      if (result.status === "succeeded") {
        setUploadProgress({ filename: file.name, status: "succeeded", progress: 100, docId: result.id });
        await fetchDocs();
        setTimeout(() => setUploadProgress(null), 2000);
      } else {
        throw new Error("Upload completed but indexing may have failed");
      }
    } catch (error: any) {
      setUploadProgress({ filename: file.name, status: "failed", progress: 0, error: error.message || "Upload failed" });
      if (error.message === "unauthorized") router.push("/auth");
      else setError(error.message || "Upload failed");
      setTimeout(() => setUploadProgress(null), 5000);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteRagDocument(id);
      setDocs((prev) => prev.filter((d) => d.id !== id));
      setError(null);
    } catch (error: any) {
      if (error.message === "unauthorized") router.push("/auth");
      else setError("Delete failed");
    }
  };

  // ── UI ────────────────────────────────────────────────────────────
  return (
    <AuthenticatedLayout title="Documents">
      <p style={{ fontSize: 13, color: "#475569", margin: "0 0 24px" }}>
        Upload financial documents to ground AI explanations with verified data.
      </p>

      {uploadProgress && (
        <UploadStatus
          filename={uploadProgress.filename}
          status={uploadProgress.status}
          progress={uploadProgress.progress}
          error={uploadProgress.error}
        />
      )}

      <UploadDropzone onUpload={handleUpload} uploading={uploading} error={error} />

      <div style={{ marginTop: 24 }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 40, color: "#475569", fontSize: 13 }}>Loading documents...</div>
        ) : docs.length === 0 ? (
          <EmptyState
            title="No documents uploaded"
            description="Upload a PDF or TXT file to help ground AI explanations with your own data."
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {docs.map((doc) => (
              <div
                key={doc.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "14px 18px",
                  background: "#1A1D27",
                  border: "1px solid #2E3248",
                  borderRadius: 10,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 14, fontWeight: 500, color: "#F1F5F9", margin: "0 0 6px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {doc.filename}
                  </p>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, color: "#475569" }}>
                      v{doc.version} · {new Date(doc.uploaded_at).toLocaleDateString()}
                    </span>
                    <span style={{
                      fontSize: 11, padding: "2px 8px", borderRadius: 99, fontWeight: 500,
                      background: doc.active ? "rgba(34,197,94,0.12)" : "rgba(71,85,105,0.2)",
                      color: doc.active ? "#22C55E" : "#475569",
                    }}>
                      {doc.active ? "Active" : "Inactive"}
                    </span>
                    <span style={{ fontSize: 11, color: "#475569" }}>
                      Trust: {Math.round(doc.trust_level * 100)}%
                    </span>
                    {doc.status && (
                      <span style={{
                        fontSize: 11, padding: "2px 8px", borderRadius: 99, fontWeight: 500,
                        background: doc.status === "succeeded" ? "rgba(99,102,241,0.12)" : "rgba(239,68,68,0.12)",
                        color: doc.status === "succeeded" ? "#6366F1" : "#EF4444",
                      }}>
                        {doc.status}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(doc.id)}
                  style={{
                    marginLeft: 16, padding: "6px 14px", borderRadius: 8, fontSize: 13,
                    color: "#EF4444", background: "transparent", border: "1px solid rgba(239,68,68,0.3)",
                    cursor: "pointer",
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(239,68,68,0.08)"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </AuthenticatedLayout>
  );
}