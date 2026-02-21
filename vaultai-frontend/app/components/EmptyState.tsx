export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void; loading?: boolean };
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
        <span className="text-3xl text-gray-400">◎</span>
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-600 max-w-md mb-4">{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          disabled={action.loading}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm
                     font-medium rounded-lg disabled:opacity-50"
        >
          {action.loading ? "Loading..." : action.label}
        </button>
      )}
    </div>
  );
}