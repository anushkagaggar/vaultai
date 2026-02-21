interface UploadStatusProps {
  filename: string;
  status: "uploading" | "processing" | "succeeded" | "failed";
  progress?: number;
  error?: string;
}

export function UploadStatus({ filename, status, progress, error }: UploadStatusProps) {
  return (
    <div className="mb-4 rounded-lg border bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        {/* Status Icon */}
        <div className="mt-0.5">
          {status === "uploading" && (
            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          )}
          {status === "processing" && (
            <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          )}
          {status === "succeeded" && (
            <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
              <span className="text-white text-xs">✓</span>
            </div>
          )}
          {status === "failed" && (
            <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center">
              <span className="text-white text-xs">✕</span>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{filename}</p>
          
          {/* Status Text */}
          <p className="text-xs text-gray-600 mt-1">
            {status === "uploading" && "Uploading..."}
            {status === "processing" && "Processing document..."}
            {status === "succeeded" && "Upload completed successfully"}
            {status === "failed" && (error || "Upload failed")}
          </p>

          {/* Progress Bar */}
          {(status === "uploading" || status === "processing") && (
            <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  status === "uploading" ? "bg-blue-500" : "bg-indigo-500"
                }`}
                style={{ width: `${progress || 50}%` }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}