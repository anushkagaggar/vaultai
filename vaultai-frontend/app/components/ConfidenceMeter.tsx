export default function ConfidenceMeter({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  const color = value >= 0.7 ? "bg-green-500" : value >= 0.4 ? "bg-yellow-500" : "bg-red-500";
  const label = value >= 0.7 ? "High" : value >= 0.4 ? "Medium" : "Low";

  return (
    <div className="flex flex-col items-end gap-1 min-w-[80px]">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">{label}</span>
        <span className="text-sm font-bold text-gray-900">{percent}%</span>
      </div>
      <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-500`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="text-[10px] text-gray-400 uppercase tracking-wide">Trust</p>
    </div>
  );
}
