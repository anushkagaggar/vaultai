"use client";
import { useEffect, useState } from 'react';
import { getDocs, deleteDoc, Document } from '@/lib/api';
import UploadDropzone from '../../components/UploadDropzone';

export default function UploadsPage() {
  const [docs, setDocs] = useState<Document[]>([]);

  const refreshDocs = () => getDocs().then(setDocs);
  useEffect(() => { refreshDocs(); }, []);

  const handleDelete = async (id: string) => {
    await deleteDoc(id);
    refreshDocs();
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">RAG Knowledge Base</h1>
      <UploadDropzone onUploadSuccess={refreshDocs} />
      
      <div className="mt-8">
        <h2 className="text-lg font-semibold mb-4">Active Documents</h2>
        <div className="space-y-2">
          {docs.map(doc => (
            <div key={doc.id} className="flex justify-between items-center p-4 border rounded bg-white">
              <div>
                <p className="font-medium">{doc.name}</p>
                <p className="text-sm text-gray-500">Status: {doc.status} • Trust: {doc.trustLevel}</p>
              </div>
              <button 
                onClick={() => handleDelete(doc.id)}
                className="text-red-600 hover:bg-red-50 px-3 py-1 rounded"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}