export function ExecutionTimeline({
  status,
  executionId,
}: {
  status: string;
  executionId: number | null;
}) {
  const stages = [
    { key: "pending", label: "Pending" },
    { key: "running", label: "Running" },
    { key: "success", label: "Complete" },
  ];

  const currentIndex = status === "pending" ? 0 : status === "running" ? 1 : 2;

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-blue-900 text-sm font-medium">Computing insight...</p>
      </div>

      {executionId && (
        <p className="text-blue-700 text-xs font-mono">
          Execution #{executionId}
        </p>
      )}

      <div className="flex items-center gap-2 mt-3">
        {stages.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-2">
            <div
              className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                i <= currentIndex
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-500"
              }`}
            >
              {i + 1}
            </div>
            <span className={`text-xs ${i <= currentIndex ? "text-blue-900" : "text-gray-500"}`}>
              {stage.label}
            </span>
            {i < stages.length - 1 && (
              <div className="w-8 h-0.5 bg-gray-300" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}