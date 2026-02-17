export default function ConfidenceMeter({ score }: { score: number }) {
  const percentage = Math.round(score * 100);
  
  // Color coding based on your Phase-5 rules
  let colorClass = 'bg-green-500';
  let textClass = 'text-green-700';
  if (score < 0.4) {
    colorClass = 'bg-red-500';
    textClass = 'text-red-700';
  } else if (score < 0.8) {
    colorClass = 'bg-yellow-500';
    textClass = 'text-yellow-700';
  }

  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-2">
        <span className={`text-sm font-medium ${textClass}`}>System Confidence</span>
        <span className={`text-sm font-bold ${textClass}`}>{percentage}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div 
          className={`${colorClass} h-2.5 rounded-full transition-all duration-500`} 
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
      {score < 0.4 && (
        <p className="text-xs text-red-600 mt-2">Warning: Degraded confidence. Manual review advised.</p>
      )}
    </div>
  );
}