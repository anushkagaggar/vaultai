"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getInsights } from "../../../lib/backend";
import type { InsightResponse } from "../../../lib/backend";

// ─── Helper Functions ────────────────────────────────────────────────────────

function fmt(n: number | undefined) {
  if (n === undefined || n === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

// ─── Sub-Components ──────────────────────────────────────────────────────────

function ConfidenceArc({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const radius = 36;
  const circ = Math.PI * radius;
  const fill = (value * circ).toFixed(1);
  
  const color = value >= 0.7 ? "#10b981" : value >= 0.4 ? "#f59e0b" : "#ef4444";
  const label = value >= 0.7 ? "High Trust" : value >= 0.4 ? "Medium" : "Low Trust";

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="90" height="52" viewBox="0 0 90 52">
        <path
          d={`M 9 46 A ${radius} ${radius} 0 0 1 81 46`}
          fill="none"
          stroke="#1e293b"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <path
          d={`M 9 46 A ${radius} ${radius} 0 0 1 81 46`}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${fill} ${circ}`}
          style={{ transition: "stroke-dasharray 1s ease" }}
        />
        <text
          x="45"
          y="44"
          textAnchor="middle"
          fill={color}
          fontSize="15"
          fontWeight="800"
          fontFamily="monospace"
        >
          {pct}%
        </text>
      </svg>
      <span className="text-[11px] font-semibold tracking-widest uppercase" style={{ color }}>
        {label}
      </span>
    </div>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
      <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-gray-100 bg-gray-50">
        <span className="text-base">{icon}</span>
        <h2 className="text-xs font-bold text-gray-700 tracking-wider uppercase">
          {title}
        </h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function MetricRow({
  label,
  value,
  mono = true,
  accent = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  accent?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span
        className={`text-sm font-semibold ${
          accent ? "text-blue-600" : "text-gray-900"
        } ${mono ? "font-mono" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}

function CategoryChart({
  categories,
}: {
  categories: { category: string; total: number }[];
}) {
  const max = Math.max(...categories.map((c) => c.total));
  const colors = [
    "from-blue-500 to-blue-400",
    "from-purple-500 to-purple-400",
    "from-cyan-500 to-cyan-400",
    "from-emerald-500 to-emerald-400",
    "from-amber-500 to-amber-400",
  ];

  return (
    <div className="space-y-3">
      {categories.map((c, i) => {
        const pct = Math.round((c.total / max) * 100);
        return (
          <div key={c.category}>
            <div className="flex justify-between mb-1.5">
              <span className="text-sm text-gray-700 capitalize font-medium">
                {c.category}
              </span>
              <span className="text-sm font-mono font-semibold text-gray-900">
                {fmt(c.total)}
              </span>
            </div>
            <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full bg-gradient-to-r ${colors[i % colors.length]} rounded-full transition-all duration-1000`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LineageItem({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-gray-100 last:border-0">
      <div className="w-1.5 h-1.5 rounded-full bg-gray-400 mt-1.5 shrink-0" />
      <div className="flex-1 flex items-center justify-between gap-4 min-w-0">
        <span className="text-sm text-gray-600 shrink-0">{label}</span>
        <span
          className={`text-sm font-mono font-semibold truncate text-right ${
            highlight ? "text-blue-600" : "text-gray-900"
          }`}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function InsightDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [insight, setInsight] = useState<InsightResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const data = await getInsights();
        
        if (!cancelled) {
          // Check if the artifact_id matches
          if (data.status === "ready" && data.artifact_id === parseInt(id)) {
            setInsight(data);
          } else {
            setError(true);
          }
        }
      } catch (err: any) {
        if (!cancelled) {
          if (err.message === "unauthorized") {
            router.push("/auth");
          } else {
            setError(true);
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [id, router]);

  const metrics = insight?.data?.metrics;

  // ─── Loading State ─────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading insight...</div>
      </div>
    );
  }

  // ─── Error State ───────────────────────────────────────────────────────────

  if (error || !insight) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-2xl mx-auto px-4 py-8">
          <Link
            href="/insights"
            className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 mb-6"
          >
            ← Back to Insights
          </Link>
          <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
            <p className="text-red-700 font-semibold mb-1">Insight Not Found</p>
            <p className="text-red-600 text-sm">
              This insight may have been invalidated or not yet computed.
            </p>
            <Link
              href="/insights"
              className="inline-block mt-4 text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              ← Go back
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ─── Main Content ──────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {/* Back Navigation */}
        <Link
          href="/insights"
          className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium"
        >
          ← Back to Insights
        </Link>

        {/* Header */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <p className="text-[10px] text-blue-600 tracking-[0.25em] uppercase font-semibold mb-2">
                Spending Trends · Artifact #{insight.artifact_id}
              </p>
              <h1 className="text-xl font-bold text-gray-900 tracking-tight mb-3">
                Full Reasoning
              </h1>

              {/* Status badges */}
              <div className="flex items-center gap-2 flex-wrap">
                {insight.degraded ? (
                  <span className="inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full bg-yellow-100 text-yellow-800 border border-yellow-200 font-semibold tracking-wide">
                    <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 animate-pulse" />
                    DEGRADED
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full bg-green-100 text-green-800 border border-green-200 font-semibold tracking-wide">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                    TRUSTED
                  </span>
                )}
                
                {insight.stable !== undefined && (
                  <span
                    className={`text-[10px] px-2.5 py-1 rounded-full font-semibold tracking-wide border ${
                      insight.stable
                        ? "bg-gray-100 text-gray-700 border-gray-300"
                        : "bg-yellow-100 text-yellow-800 border-yellow-200"
                    }`}
                  >
                    {insight.stable ? "FRESH" : "STALE"}
                  </span>
                )}
                
                {metrics?.trend_type && (
                  <span className="text-[10px] px-2.5 py-1 rounded-full font-semibold tracking-wide bg-blue-100 text-blue-800 border border-blue-200 capitalize">
                    {metrics.trend_type}
                  </span>
                )}
              </div>

              {insight.created_at && (
                <p className="text-[11px] text-gray-500 font-mono mt-3">
                  Generated {new Date(insight.created_at).toLocaleString()}
                </p>
              )}
            </div>

            {/* Confidence arc */}
            <div className="shrink-0">
              <ConfidenceArc value={insight.confidence ?? 0} />
            </div>
          </div>
        </div>

        {/* AI Explanation */}
        <Section title="AI Explanation" icon="◎">
          {insight.degraded || !insight.data?.summary ? (
            <div className="rounded-xl bg-yellow-50 border border-yellow-200 p-4">
              <p className="text-xs font-bold text-yellow-900 uppercase tracking-wider mb-2">
                Explanation Unavailable
              </p>
              <p className="text-sm text-yellow-800 leading-relaxed">
                The AI-generated explanation did not pass numeric validation. The
                metrics below are accurate and sourced directly from your expense
                data.
              </p>
            </div>
          ) : (
            <div className="rounded-xl bg-gray-50 border border-gray-200 p-4">
              <p className="text-sm text-gray-800 leading-relaxed">
                {insight.data.summary}
              </p>
            </div>
          )}
        </Section>

        {/* Rolling Averages */}
        {metrics && (
          <Section title="Rolling Averages" icon="◈">
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "30-Day", value: metrics.rolling["30_day_avg"] },
                { label: "60-Day", value: metrics.rolling["60_day_avg"] },
                { label: "90-Day", value: metrics.rolling["90_day_avg"] },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-xl bg-gray-50 border border-gray-200 p-4 text-center"
                >
                  <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-1.5 font-semibold">
                    {label}
                  </p>
                  <p className="text-base font-bold text-gray-900 font-mono">
                    {fmt(value)}
                  </p>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Monthly Comparison */}
        {metrics && (
          <Section title="Monthly Comparison" icon="◑">
            <MetricRow
              label="Previous Month"
              value={fmt(metrics.monthly.previous_month)}
            />
            <MetricRow
              label="Current Month"
              value={fmt(metrics.monthly.current_month)}
            />
            <MetricRow
              label="Percent Change"
              value={`${metrics.monthly.percent_change > 0 ? "+" : ""}${
                metrics.monthly.percent_change
              }%`}
              accent={Math.abs(metrics.monthly.percent_change) > 20}
            />
          </Section>
        )}

        {/* Category Breakdown */}
        {metrics?.categories && (
          <Section title="Category Breakdown" icon="◷">
            <CategoryChart categories={metrics.categories} />
          </Section>
        )}

        {/* System Lineage */}
        <Section title="System Lineage" icon="◌">
          <LineageItem
            label="Artifact ID"
            value={`#${insight.artifact_id ?? "—"}`}
            highlight
          />
          <LineageItem
            label="Generated From"
            value={
              insight.generated_from_execution
                ? `Execution #${insight.generated_from_execution}`
                : "—"
            }
          />
          <LineageItem
            label="Pipeline Version"
            value={insight.pipeline_version ?? "—"}
          />
          <LineageItem
            label="Freshness"
            value={insight.stable ? "Fresh" : "Stale"}
          />
          <LineageItem
            label="Computed At"
            value={
              insight.created_at
                ? new Date(insight.created_at).toLocaleString()
                : "—"
            }
          />

          <div className="mt-4 pt-4 border-t border-gray-100 rounded-xl bg-blue-50 p-3">
            <p className="text-[10px] text-blue-800 leading-relaxed">
              This insight was produced by a deterministic pipeline (Phase 3) and
              validated by a numeric consistency engine (Phase 4). The explanation
              was accepted only after passing structural, numeric, and language
              guards.
            </p>
          </div>
        </Section>

        {/* Bottom Navigation */}
        <div className="flex justify-between pt-2">
          <Link
            href="/insights"
            className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
          >
            ← All Insights
          </Link>
          <Link
            href="/runs"
            className="text-sm text-blue-600 hover:text-blue-700 transition-colors"
          >
            View execution monitor →
          </Link>
        </div>
      </div>
    </div>
  );
}