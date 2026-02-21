// app/components/InsightCard.tsx
import Link from "next/link";
import ConfidenceMeter from "./ConfidenceMeter";
import {StatusBadge} from "./StatusBadge";
import {ExplanationBlock} from "./ExplanationBlock";

interface InsightCardProps {
  insight: {
    artifact_id?: number;
    confidence: number;
    degraded: boolean;
    data?: {
      summary: string;
      explanation: string | null;
      metrics: {
        rolling: { "30_day_avg": number; "60_day_avg": number; "90_day_avg": number };
        monthly: { current_month: number; previous_month: number; percent_change: number };
        trend_type: string;
        categories: { category: string; total: number }[];
      };
    };
    created_at?: string;
  };
}

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function relativeTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function InsightCard({ insight }: InsightCardProps) {
  const { confidence, degraded, data, artifact_id, created_at } = insight;
  const metrics = data?.metrics;
  const isLowConfidence = confidence < 0.4;

  return (
    <div
      className={`rounded-lg border p-6 transition-all ${
        isLowConfidence
          ? "opacity-60 border-gray-300 bg-gray-50"
          : degraded
          ? "border-yellow-300 bg-yellow-50"
          : "border-blue-200 bg-white shadow-sm hover:shadow-md"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-lg font-semibold text-gray-900">
              Spending Trends
            </h2>
            <StatusBadge degraded={degraded} confidence={confidence} />
          </div>
          {created_at && (
            <p className="text-xs text-gray-500">
              {relativeTime(created_at)}
            </p>
          )}
        </div>
        <ConfidenceMeter value={confidence} />
      </div>

      {/* Explanation */}
      <div className="mb-4">
        <ExplanationBlock
          summary={data?.summary || null}
          degraded={degraded}
        />
      </div>

      {/* Metrics Grid */}
      {metrics && (
        <div className="grid grid-cols-3 gap-2 mb-4">
          <MetricBox
            label="30d Avg"
            value={fmt(metrics.rolling["30_day_avg"])}
          />
          <MetricBox
            label="This Month"
            value={fmt(metrics.monthly.current_month)}
          />
          <MetricBox
            label="Change"
            value={`${metrics.monthly.percent_change > 0 ? "+" : ""}${metrics.monthly.percent_change}%`}
            highlight
          />
        </div>
      )}

      {/* Footer */}
      {artifact_id && (
        <div className="pt-4 border-t border-gray-200">
          <Link
            href={`/insights/${artifact_id}`}
            className="text-sm text-blue-600 hover:text-blue-700 hover:underline"
          >
            View full reasoning →
          </Link>
        </div>
      )}
    </div>
  );
}

function MetricBox({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="bg-gray-50 rounded p-3">
      <p className="text-xs text-gray-600 mb-1">{label}</p>
      <p
        className={`text-sm font-semibold ${
          highlight ? "text-blue-700" : "text-gray-900"
        }`}
      >
        {value}
      </p>
    </div>
  );
}