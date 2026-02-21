"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getRagDocuments, uploadRagDocument} from "../../lib/backend";
import type { RagDocument } from "../../lib/backend";
import { UploadDropzone } from "../components/UploadDropzone";
import { EmptyState } from "../components/EmptyState";

export default function UploadsPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<RagDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDocs = async () => {
    try {
      console.log("Fetching documents from:", `${process.env.NEXT_PUBLIC_API_URL}/rag/documents`);
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

  const handleUpload = async (file: File) => {
    const allowed = ["application/pdf", "text/plain"];
    if (!allowed.includes(file.type)) {
      setError("Only PDF and TXT files are supported");
      return;
    }

    setUploading(true);
    setError(null);

    try {
      console.log("Uploading file:", file.name);
      await uploadRagDocument(file);
      await fetchDocs();
    } catch (error: any) {
      console.error("Upload error:", error);
      if (error.message === "unauthorized") {
        router.push("/auth");
      } else {
        setError(error.message || "Upload failed");
      }
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Documents</h1>
      <p className="text-sm text-gray-600 mb-6">
        Upload financial documents to ground AI explanations
      </p>

      <UploadDropzone onUpload={handleUpload} uploading={uploading} error={error} />

      <div className="mt-6">
        {loading ? (
          <div className="text-center py-8 text-gray-400 text-sm">Loading...</div>
        ) : docs.length === 0 ? (
          <EmptyState title="No documents" description="Upload a PDF or TXT file to get started." />
        ) : (
          <div className="space-y-3">
            {docs.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between p-4 border rounded-lg bg-white"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">{doc.filename}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-gray-500">
                      v{doc.version} · {new Date(doc.uploaded_at).toLocaleDateString()}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        doc.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {doc.active ? "Active" : "Inactive"}
                    </span>
                    <span className="text-xs text-gray-500">
                      Trust: {Math.round(doc.trust_level * 100)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}