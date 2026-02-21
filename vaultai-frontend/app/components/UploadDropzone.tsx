import { useRef } from "react";

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

  const handleClick = () => fileRef.current?.click();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
  };

  return (
    <div>
      <div
        onClick={handleClick}
        className="border-2 border-dashed border-gray-300 rounded-lg p-8
                   hover:border-blue-400 transition-colors cursor-pointer
                   flex flex-col items-center justify-center gap-3"
      >
        <div className="text-4xl">📄</div>
        <p className="text-gray-700 text-sm font-medium">
          {uploading ? "Uploading..." : "Click to upload PDF or TXT"}
        </p>
        <p className="text-gray-500 text-xs">
          Documents help ground AI explanations
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt"
          onChange={handleChange}
          className="hidden"
        />
      </div>

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          ⚠ {error}
        </div>
      )}
    </div>
  );
}