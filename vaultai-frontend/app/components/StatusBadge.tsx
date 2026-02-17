export default function StatusBadge({ status }: { status: 'trusted' | 'degraded' }) {
  const isTrusted = status === 'trusted';
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium uppercase tracking-wider ${
      isTrusted ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
    }`}>
      {status}
    </span>
  );
}