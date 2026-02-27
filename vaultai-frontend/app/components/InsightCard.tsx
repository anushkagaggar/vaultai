import Link from "next/link";
import ConfidenceMeter from "./ConfidenceMeter";
import { StatusBadge } from "./StatusBadge";
import { ExplanationBlock } from "./ExplanationBlock";

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
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
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

const CATEGORY_COLORS: Record<string, string> = {
  food:          "#F97316",
  transport:     "#3B82F6",
  shopping:      "#EC4899",
  utilities:     "#8B5CF6",
  health:        "#10B981",
  entertainment: "#F59E0B",
  other:         "#6B7280",
};

function getCategoryColor(cat: string) {
  return CATEGORY_COLORS[cat.toLowerCase()] ?? "#6B7280";
}

export default function InsightCard({ insight }: InsightCardProps) {
  const { confidence, degraded, data, artifact_id, created_at } = insight;
  const metrics = data?.metrics;
  const change = metrics?.monthly.percent_change ?? 0;
  const isPositive = change > 0;

  return (
    <div
      style={{
        background: "#1A1D27",
        border: degraded
          ? "1px solid rgba(245,158,11,0.3)"
          : "1px solid #2E3248",
        borderRadius: 14,
        padding: 24,
        boxShadow: "0 1px 3px rgba(0,0,0,0.4), 0 4px 16px rgba(0,0,0,0.15)",
      }}
    >
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: "#F1F5F9", margin: 0 }}>
              Spending Trends
            </h2>
            <StatusBadge degraded={degraded} confidence={confidence} />
          </div>
          {created_at && (
            <p style={{ fontSize: 12, color: "#475569", margin: 0 }}>
              {relativeTime(created_at)}
            </p>
          )}
        </div>
        <ConfidenceMeter value={confidence} />
      </div>

      {/* Explanation */}
      <div style={{ marginBottom: 20 }}>
        <ExplanationBlock summary={data?.summary ?? null} degraded={degraded} />
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: "#2E3248", marginBottom: 20 }} />

      {/* Metrics grid */}
      {metrics && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 12,
            marginBottom: 20,
          }}
        >
          {[
            { label: "30-Day Avg",   value: fmt(metrics.rolling["30_day_avg"]) },
            { label: "60-Day Avg",   value: fmt(metrics.rolling["60_day_avg"]) },
            { label: "90-Day Avg",   value: fmt(metrics.rolling["90_day_avg"]) },
            {
              label: "Month Change",
              value: `${isPositive ? "+" : ""}${change}%`,
              accent: isPositive ? "#EF4444" : "#22C55E",
            },
          ].map(({ label, value, accent }) => (
            <div
              key={label}
              style={{
                background: "#22263A",
                border: "1px solid #2E3248",
                borderRadius: 10,
                padding: "12px 14px",
              }}
            >
              <p style={{ fontSize: 11, color: "#475569", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {label}
              </p>
              <p
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: accent ?? "#F1F5F9",
                  margin: 0,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {value}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Category bars */}
      {metrics?.categories && metrics.categories.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <p style={{ fontSize: 11, color: "#475569", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
            Category Breakdown
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {metrics.categories.slice(0, 5).map((cat) => {
              const max = Math.max(...metrics.categories.map((c) => c.total));
              const pct = Math.round((cat.total / max) * 100);
              const color = getCategoryColor(cat.category);
              return (
                <div key={cat.category}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                    <span style={{ fontSize: 13, color: "#94A3B8", textTransform: "capitalize" }}>
                      {cat.category}
                    </span>
                    <span style={{ fontSize: 12, color: "#475569", fontFamily: "monospace" }}>
                      {fmt(cat.total)}
                    </span>
                  </div>
                  <div style={{ height: 5, background: "#22263A", borderRadius: 99, overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${pct}%`,
                        background: color,
                        borderRadius: 99,
                        transition: "width 0.6s ease",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Footer */}
      {artifact_id && (
        <div style={{ paddingTop: 16, borderTop: "1px solid #2E3248" }}>
          <Link
            href={`/insights/${artifact_id}`}
            style={{ fontSize: 14, color: "#6366F1", textDecoration: "none", fontWeight: 500 }}
          >
            View full reasoning →
          </Link>
        </div>
      )}
    </div>
  );
}