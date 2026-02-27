"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSystemMetrics } from "../../lib/backend";
import type { SystemMetrics } from "../../lib/backend";
import AuthenticatedLayout from "../components/Authenticatedlayout";

export default function RunsPage() {
  const router = useRouter();
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  // ── ALL original logic kept ───────────────────────────────────────
  useEffect(() => {
    const fetch_ = async () => {
      try {
        const data = await getSystemMetrics();
        setMetrics(data);
      } catch (error: any) {
        if (error.message === "unauthorized") router.push("/auth");
      } finally {
        setLoading(false);
      }
    };
    fetch_();
  }, [router]);

  // ── UI ────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <AuthenticatedLayout title="Execution Monitor">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200 }}>
          <span style={{ fontSize: 13, color: "#475569" }}>Loading metrics...</span>
        </div>
      </AuthenticatedLayout>
    );
  }

  if (!metrics) {
    return (
      <AuthenticatedLayout title="Execution Monitor">
        <p style={{ color: "#EF4444", fontSize: 14 }}>Failed to load metrics.</p>
      </AuthenticatedLayout>
    );
  }

  return (
    <AuthenticatedLayout title="Execution Monitor">

      {/* Execution counts */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Total",    value: metrics.executions.total,    color: "#6366F1", bg: "rgba(99,102,241,0.08)",   border: "rgba(99,102,241,0.2)" },
          { label: "Success",  value: metrics.executions.success,  color: "#22C55E", bg: "rgba(34,197,94,0.08)",   border: "rgba(34,197,94,0.2)" },
          { label: "Fallback", value: metrics.executions.fallback, color: "#F59E0B", bg: "rgba(245,158,11,0.08)",  border: "rgba(245,158,11,0.2)" },
          { label: "Failed",   value: metrics.executions.failed,   color: "#EF4444", bg: "rgba(239,68,68,0.08)",   border: "rgba(239,68,68,0.2)" },
        ].map(({ label, value, color, bg, border }) => (
          <div key={label} style={{ background: bg, border: `1px solid ${border}`, borderRadius: 12, padding: "16px 20px" }}>
            <p style={{ fontSize: 11, color, margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>{label}</p>
            <p style={{ fontSize: 28, fontWeight: 700, color, margin: 0, fontFamily: "monospace" }}>{value}</p>
          </div>
        ))}
      </div>

      {/* System Rates */}
      <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, padding: "20px 24px", marginBottom: 16 }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 16px" }}>System Rates</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {[
            { label: "Success Rate",   value: metrics.rates.success_rate,   color: "#22C55E" },
            { label: "Fallback Rate",  value: metrics.rates.fallback_rate,  color: "#F59E0B" },
            { label: "Cache Hit Rate", value: metrics.rates.cache_hit_rate, color: "#6366F1" },
          ].map(({ label, value, color }) => {
            const pct = Math.round(value * 100);
            return (
              <div key={label}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 13, color: "#94A3B8" }}>{label}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color, fontFamily: "monospace" }}>{pct}%</span>
                </div>
                <div style={{ height: 6, background: "#22263A", borderRadius: 99, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 99, transition: "width 0.6s ease" }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Performance */}
      <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, padding: "20px 24px" }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 16px" }}>Performance</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          {[
            { label: "Avg Execution Time", value: `${metrics.performance.avg_execution_time_seconds}s` },
            { label: "Total Artifacts",    value: String(metrics.artifacts.total) },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid #2E3248" }}>
              <span style={{ fontSize: 13, color: "#94A3B8" }}>{label}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#F1F5F9", fontFamily: "monospace" }}>{value}</span>
            </div>
          ))}
        </div>
      </div>

    </AuthenticatedLayout>
  );
}