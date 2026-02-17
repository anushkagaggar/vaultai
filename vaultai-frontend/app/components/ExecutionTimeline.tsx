import { ExecutionRun } from '@/lib/api';

export default function ExecutionTimeline({ execution }: { execution: ExecutionRun }) {
  const statusColors = {
    pending: 'bg-gray-200 text-gray-600',
    running: 'bg-blue-100 text-blue-600 animate-pulse',
    success: 'bg-green-100 text-green-700',
    fallback: 'bg-yellow-100 text-yellow-700',
    failed: 'bg-red-100 text-red-700'
  };

  return (
    <div className="flex items-center gap-4 p-4 border rounded-lg bg-white shadow-sm">
      <div className="flex-1">
        <p className="text-sm font-mono text-gray-500">Run ID: {execution.id}</p>
        <p className="text-xs text-gray-400 mt-1">Started: {new Date(execution.startedAt).toLocaleTimeString()}</p>
      </div>
      
      <div className={`px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide ${statusColors[execution.status]}`}>
        {execution.status}
      </div>
    </div>
  );
}