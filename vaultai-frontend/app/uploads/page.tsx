"use client";

import { useEffect, useState, useRef } from "react";

interface Document {
  id: number;
  filename: string;
  trust_level: number;
  active: boolean;
  uploaded_at: string;
  version: number;
}

export default function UploadsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const token = typeof window !== "undefined"
    ? localStorage.getItem("token") : null;
  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchDocs = async () => {
    try {
      const res = await fetch(`${API}/rag/documents`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setDocs(data);
    } catch {
      setError("Failed to load documents.");
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowed = ["application/pdf", "text/plain"];
    if (!allowed.includes(file.type)) {
      setError("Only PDF and TXT files are supported.");
      return;
    }

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API}/rag/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        setError(err.detail || "Upload failed.");
      } else {
        await fetchDocs();
      }
    } catch {
      setError("Upload failed. Please try again.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await fetch(`${API}/rag/documents/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      setDocs(prev => prev.filter(d => d.id !== id));
    } catch {
      setError("Delete failed.");
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Documents</h1>

      {/* Upload Area */}
      <div
        className="border-2 border-dashed border-gray-300 rounded-xl p-8
                   flex flex-col items-center justify-center gap-3
                   hover:border-indigo-400 transition-colors cursor-pointer"
        onClick={() => fileRef.current?.click()}
      >
        <div className="text-3xl">📄</div>
        <p className="text-gray-600 text-sm font-medium">
          {uploading ? "Uploading..." : "Click to upload PDF or TXT"}
        </p>
        <p className="text-gray-400 text-xs">
          Documents are used to ground AI explanations
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt"
          onChange={handleUpload}
          className="hidden"
        />
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* Document List */}
      {docs.length === 0 ? (
        <div className="text-center py-8 text-gray-400 text-sm">
          No documents uploaded yet.
        </div>
      ) : (
        <div className="space-y-3">
          {docs.map(doc => (
            <div
              key={doc.id}
              className="flex items-center justify-between p-4
                         border border-gray-200 rounded-xl bg-white"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">
                  {doc.filename}
                </p>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-gray-400">
                    v{doc.version} · {new Date(doc.uploaded_at).toLocaleDateString()}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    doc.active
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-500"
                  }`}>
                    {doc.active ? "Active" : "Inactive"}
                  </span>
                  <span className="text-xs text-gray-400">
                    Trust: {Math.round(doc.trust_level * 100)}%
                  </span>
                </div>
              </div>
              <button
                onClick={() => handleDelete(doc.id)}
                className="text-red-400 hover:text-red-600 text-sm px-3 py-1
                           rounded-lg hover:bg-red-50 transition-colors"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}