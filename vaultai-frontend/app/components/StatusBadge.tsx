export function StatusBadge({ degraded, confidence }: { degraded: boolean; confidence: number }) {
  if (degraded) {
    return (
      <span className="px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800 rounded-full">
        ⚠ Degraded
      </span>
    );
  }

  if (confidence < 0.4) {
    return (
      <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-full">
        Low Trust
      </span>
    );
  }

  return (
    <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded-full">
      ✓ Trusted
    </span>
  );
}