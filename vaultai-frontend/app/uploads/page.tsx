"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getRagDocuments,
  uploadRagDocument,
  deleteRagDocument,
  getDocumentStatus,
} from "../../lib/backend";
import type { RagDocument } from "../../lib/backend";
import { UploadDropzone } from "../components/UploadDropzone";
import { EmptyState } from "../components/EmptyState";
import { UploadStatus } from "../components/UploadStatus";

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

  // Fetch documents
  const fetchDocs = async () => {
    try {
      console.log("Fetching documents...");
      const data = await getRagDocuments();
      console.log("Documents response:", data);
      setDocs(data);
      setError(null);
    } catch (error: any) {
      console.error("Fetch documents error:", error);
      if (error.message === "unauthorized") {
        router.push("/auth");
      } else {
        setError("Failed to load documents");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  // Handle upload with status tracking
  const handleUpload = async (file: File) => {
    const allowed = ["application/pdf", "text/plain"];
    if (!allowed.includes(file.type)) {
      setError("Only PDF and TXT files are supported");
      return;
    }

    setUploading(true);
    setError(null);

    // Initialize upload progress
    setUploadProgress({
      filename: file.name,
      status: "uploading",
      progress: 0,
    });

    try {
      // Simulate upload progress (since we can't track real upload progress easily)
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (!prev || prev.progress >= 90) return prev;
          return { ...prev, progress: prev.progress + 10 };
        });
      }, 200);

      console.log("Uploading file:", file.name);
      const result = await uploadRagDocument(file);

      clearInterval(progressInterval);

      // Update to processing
      setUploadProgress({
        filename: file.name,
        status: "processing",
        progress: 95,
        docId: result.id,
      });

      // Wait a bit for indexing
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Check final status
      if (result.status === "succeeded") {
        setUploadProgress({
          filename: file.name,
          status: "succeeded",
          progress: 100,
          docId: result.id,
        });

        // Refresh document list
        await fetchDocs();

        // Clear progress after 2 seconds
        setTimeout(() => {
          setUploadProgress(null);
        }, 2000);
      } else {
        throw new Error("Upload completed but indexing may have failed");
      }
    } catch (error: any) {
      console.error("Upload error:", error);

      setUploadProgress({
        filename: file.name,
        status: "failed",
        progress: 0,
        error: error.message || "Upload failed",
      });

      if (error.message === "unauthorized") {
        router.push("/auth");
      } else {
        setError(error.message || "Upload failed");
      }

      // Clear failed status after 5 seconds
      setTimeout(() => {
        setUploadProgress(null);
      }, 5000);
    } finally {
      setUploading(false);
    }
  };

  // Handle delete
  const handleDelete = async (id: number) => {
    try {
      console.log("Deleting document:", id);
      await deleteRagDocument(id);
      setDocs((prev) => prev.filter((d) => d.id !== id));
      setError(null);
    } catch (error: any) {
      console.error("Delete error:", error);
      if (error.message === "unauthorized") {
        router.push("/auth");
      } else {
        setError("Delete failed");
      }
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Documents</h1>
      <p className="text-sm text-gray-600 mb-6">
        Upload financial documents to ground AI explanations
      </p>

      {/* Upload Progress Status */}
      {uploadProgress && (
        <UploadStatus
          filename={uploadProgress.filename}
          status={uploadProgress.status}
          progress={uploadProgress.progress}
          error={uploadProgress.error}
        />
      )}

      {/* Upload Dropzone */}
      <UploadDropzone onUpload={handleUpload} uploading={uploading} error={error} />

      {/* Document List */}
      <div className="mt-6">
        {loading ? (
          <div className="text-center py-8 text-gray-400 text-sm">Loading...</div>
        ) : docs.length === 0 ? (
          <EmptyState
            title="No documents"
            description="Upload a PDF or TXT file to get started."
          />
        ) : (
          <div className="space-y-3">
            {docs.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between p-4 border rounded-lg bg-white hover:border-gray-300 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {doc.filename}
                  </p>
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    <span className="text-xs text-gray-500">
                      v{doc.version} · {new Date(doc.uploaded_at).toLocaleDateString()}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        doc.active
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {doc.active ? "Active" : "Inactive"}
                    </span>
                    <span className="text-xs text-gray-500">
                      Trust: {Math.round(doc.trust_level * 100)}%
                    </span>
                    {doc.status && (
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          doc.status === "succeeded"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {doc.status}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(doc.id)}
                  className="ml-4 text-red-500 hover:text-red-700 text-sm px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}