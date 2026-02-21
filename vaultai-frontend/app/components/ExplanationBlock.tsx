export function ExplanationBlock({
  summary,
  degraded,
}: {
  summary: string | null;
  degraded: boolean;
}) {
  if (degraded || !summary) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-yellow-900 text-sm font-medium mb-1">
          Explanation Unavailable
        </p>
        <p className="text-yellow-800 text-sm">
          The AI explanation failed validation. Metrics are still accurate.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <p className="text-gray-800 text-sm leading-relaxed">{summary}</p>
    </div>
  );
}