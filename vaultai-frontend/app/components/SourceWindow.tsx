export default function SourceWindow({ metrics }: { metrics: Record<string, any> }) {
  return (
    <div className="bg-gray-900 rounded-lg overflow-hidden shadow-sm">
      <div className="bg-gray-800 px-4 py-2 border-b border-gray-700 flex justify-between items-center">
        <h3 className="text-xs font-mono text-gray-400 uppercase tracking-wider">Metrics Payload</h3>
      </div>
      <div className="p-4 overflow-x-auto">
        <pre className="text-sm font-mono text-green-400">
          {JSON.stringify(metrics, null, 2)}
        </pre>
      </div>
    </div>
  );
}