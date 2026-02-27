"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getInsights } from "../../../lib/backend";
import type { InsightResponse } from "../../../lib/backend";
import AuthenticatedLayout from "../../components/Authenticatedlayout";

function fmt(n: number | undefined) {
  if (n === undefined || n === null) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}

function ConfidenceArc({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const circ = Math.PI * 36;
  const fill = (value * circ).toFixed(1);
  const color = value >= 0.7 ? "#22C55E" : value >= 0.4 ? "#F59E0B" : "#EF4444";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg width="96" height="58" viewBox="0 0 96 58">
        <path d="M 9 52 A 36 36 0 0 1 87 52" fill="none" stroke="#2E3248" strokeWidth="6" strokeLinecap="round" />
        <path d="M 9 52 A 36 36 0 0 1 87 52" fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={`${fill} ${circ}`} style={{ transition: "stroke-dasharray 1s ease" }} />
        <text x="48" y="50" textAnchor="middle" fill={color} fontSize="16" fontWeight="800" fontFamily="monospace">{pct}%</text>
      </svg>
      <span style={{ fontSize: 10, fontWeight: 600, color, textTransform: "uppercase", letterSpacing: "0.12em" }}>
        {value >= 0.7 ? "High Trust" : value >= 0.4 ? "Medium" : "Low Trust"}
      </span>
    </div>
  );
}

function Card({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, overflow: "hidden", marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 20px", borderBottom: "1px solid #2E3248", background: "#22263A" }}>
        <span style={{ fontSize: 14 }}>{icon}</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em" }}>{title}</span>
      </div>
      <div style={{ padding: 20 }}>{children}</div>
    </div>
  );
}

function MetricRow({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid #2E3248" }}>
      <span style={{ fontSize: 13, color: "#94A3B8" }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: accent ? "#6366F1" : "#F1F5F9", fontFamily: "monospace" }}>{value}</span>
    </div>
  );
}

export default function InsightDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [insight, setInsight] = useState<InsightResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // ── ALL original logic kept ───────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await getInsights();
        if (!cancelled) {
          if (data.status === "ready" && data.artifact_id === parseInt(id)) setInsight(data);
          else setError(true);
        }
      } catch (err: any) {
        if (!cancelled) {
          if (err.message === "unauthorized") router.push("/auth");
          else setError(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [id, router]);

  const metrics = insight?.data?.metrics;

  if (loading) {
    return (
      <AuthenticatedLayout title="Insight Detail">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200 }}>
          <span style={{ fontSize: 13, color: "#475569" }}>Loading insight...</span>
        </div>
      </AuthenticatedLayout>
    );
  }

  if (error || !insight) {
    return (
      <AuthenticatedLayout title="Insight Detail">
        <Link href="/insights" style={{ fontSize: 13, color: "#6366F1", textDecoration: "none", display: "inline-block", marginBottom: 20 }}>← Back to Insights</Link>
        <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: 12, padding: 32, textAlign: "center" }}>
          <p style={{ fontSize: 15, fontWeight: 600, color: "#EF4444", margin: "0 0 6px" }}>Insight Not Found</p>
          <p style={{ fontSize: 13, color: "#94A3B8", margin: 0 }}>This insight may have been invalidated or not yet computed.</p>
        </div>
      </AuthenticatedLayout>
    );
  }

  return (
    <AuthenticatedLayout title={`Insight #${insight.artifact_id}`}>
      <Link href="/insights" style={{ fontSize: 13, color: "#6366F1", textDecoration: "none", display: "inline-block", marginBottom: 24 }}>← Back to Insights</Link>

      {/* Header card */}
      <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 14, padding: 24, marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: 10, color: "#6366F1", textTransform: "uppercase", letterSpacing: "0.2em", fontWeight: 600, margin: "0 0 8px" }}>
              Spending Trends · Artifact #{insight.artifact_id}
            </p>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: "#F1F5F9", margin: "0 0 14px" }}>Full Reasoning</h1>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {insight.degraded ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 10px", borderRadius: 99, fontSize: 11, fontWeight: 600, background: "rgba(245,158,11,0.12)", color: "#F59E0B", border: "1px solid rgba(245,158,11,0.2)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#F59E0B", display: "inline-block" }} /> Degraded
                </span>
              ) : (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 10px", borderRadius: 99, fontSize: 11, fontWeight: 600, background: "rgba(34,197,94,0.12)", color: "#22C55E", border: "1px solid rgba(34,197,94,0.2)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#22C55E", display: "inline-block" }} /> Trusted
                </span>
              )}
              {metrics?.trend_type && (
                <span style={{ padding: "3px 10px", borderRadius: 99, fontSize: 11, fontWeight: 600, background: "rgba(99,102,241,0.12)", color: "#6366F1", border: "1px solid rgba(99,102,241,0.2)", textTransform: "capitalize" }}>
                  {metrics.trend_type}
                </span>
              )}
            </div>

            {insight.created_at && (
              <p style={{ fontSize: 11, color: "#475569", fontFamily: "monospace", margin: "12px 0 0" }}>
                Generated {new Date(insight.created_at).toLocaleString()}
              </p>
            )}
          </div>
          <ConfidenceArc value={insight.confidence ?? 0} />
        </div>
      </div>

      {/* AI Explanation */}
      <Card title="AI Explanation" icon="✦">
        {insight.degraded || !insight.data?.summary ? (
          <div style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)", borderRadius: 10, padding: "12px 16px" }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: "#F59E0B", margin: "0 0 4px" }}>Explanation Unavailable</p>
            <p style={{ fontSize: 13, color: "#94A3B8", margin: 0, lineHeight: 1.6 }}>
              The AI explanation failed validation. Metrics are still accurate and sourced from your expense data.
            </p>
          </div>
        ) : (
          <div style={{ background: "#22263A", border: "1px solid #2E3248", borderLeft: "3px solid #6366F1", borderRadius: 10, padding: "14px 16px" }}>
            <p style={{ fontSize: 14, color: "#94A3B8", margin: 0, lineHeight: 1.7 }}>{insight.data.summary}</p>
          </div>
        )}
      </Card>

      {/* Rolling Averages */}
      {metrics && (
        <Card title="Rolling Averages" icon="◈">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
            {[
              { label: "30-Day Avg", value: metrics.rolling["30_day_avg"] },
              { label: "60-Day Avg", value: metrics.rolling["60_day_avg"] },
              { label: "90-Day Avg", value: metrics.rolling["90_day_avg"] },
            ].map(({ label, value }) => (
              <div key={label} style={{ background: "#22263A", border: "1px solid #2E3248", borderRadius: 10, padding: "14px 16px", textAlign: "center" }}>
                <p style={{ fontSize: 11, color: "#475569", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</p>
                <p style={{ fontSize: 16, fontWeight: 700, color: "#F1F5F9", margin: 0, fontFamily: "monospace" }}>{fmt(value)}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Monthly Comparison */}
      {metrics && (
        <Card title="Monthly Comparison" icon="◑">
          <MetricRow label="Previous Month" value={fmt(metrics.monthly.previous_month)} />
          <MetricRow label="Current Month" value={fmt(metrics.monthly.current_month)} />
          <MetricRow label="Change" value={`${metrics.monthly.percent_change > 0 ? "+" : ""}${metrics.monthly.percent_change}%`}
            accent={Math.abs(metrics.monthly.percent_change) > 20} />
        </Card>
      )}

      {/* Categories */}
      {metrics?.categories && (
        <Card title="Category Breakdown" icon="◷">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {metrics.categories.map((c, i) => {
              const max = Math.max(...metrics.categories.map((x) => x.total));
              const pct = Math.round((c.total / max) * 100);
              const colors = ["#6366F1","#8B5CF6","#06B6D4","#10B981","#F59E0B"];
              return (
                <div key={c.category}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 13, color: "#94A3B8", textTransform: "capitalize" }}>{c.category}</span>
                    <span style={{ fontSize: 12, color: "#475569", fontFamily: "monospace" }}>{fmt(c.total)}</span>
                  </div>
                  <div style={{ height: 6, background: "#22263A", borderRadius: 99, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: colors[i % colors.length], borderRadius: 99, transition: "width 0.8s ease" }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* System Lineage */}
      <Card title="System Lineage" icon="◌">
        <MetricRow label="Artifact ID" value={`#${insight.artifact_id ?? "—"}`} accent />
        <MetricRow label="Generated From" value={insight.generated_from_execution ? `Execution #${insight.generated_from_execution}` : "—"} />
        <MetricRow label="Pipeline Version" value={insight.pipeline_version ?? "—"} />
        <MetricRow label="Freshness" value={insight.stable ? "Fresh" : "Stale"} />
        <MetricRow label="Computed At" value={insight.created_at ? new Date(insight.created_at).toLocaleString() : "—"} />
        <div style={{ marginTop: 16, padding: "12px 14px", background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)", borderRadius: 8 }}>
          <p style={{ fontSize: 11, color: "#6366F1", margin: 0, lineHeight: 1.6 }}>
            This insight was produced by a deterministic pipeline and validated by a numeric consistency engine. The explanation was accepted only after passing structural, numeric, and language guards.
          </p>
        </div>
      </Card>

      {/* Footer nav */}
      <div style={{ display: "flex", justifyContent: "space-between", paddingTop: 8 }}>
        <Link href="/insights" style={{ fontSize: 13, color: "#475569", textDecoration: "none" }}>← All Insights</Link>
        <Link href="/runs" style={{ fontSize: 13, color: "#6366F1", textDecoration: "none" }}>View Execution Monitor →</Link>
      </div>
    </AuthenticatedLayout>
  );
}