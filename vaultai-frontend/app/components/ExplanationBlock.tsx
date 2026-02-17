export default function ExplanationBlock({ text }: { text: string }) {
  return (
    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        Intelligence Explanation
      </h3>
      <div className="prose prose-sm text-gray-700 max-w-none whitespace-pre-wrap">
        {text || "No explanation provided for this artifact."}
      </div>
    </div>
  );
}