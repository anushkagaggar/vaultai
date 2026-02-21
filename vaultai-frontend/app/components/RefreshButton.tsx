export function RefreshButton({
  onClick,
  loading,
}: {
  onClick: () => void;
  loading: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700
                 text-white text-sm font-medium rounded-lg transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading ? (
        <>
          <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          Computing...
        </>
      ) : (
        <>
          <span>↻</span>
          Refresh Insight
        </>
      )}
    </button>
  );
}