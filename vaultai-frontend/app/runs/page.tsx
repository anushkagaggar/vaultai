"use client";

import { useEffect, useState } from "react";

interface Metrics {
  executions: {
    total: number;
    success: number;
    fallback: number;
    failed: number;
  };
  rates: {
    success_rate: number;
    fallback_rate: number;
    cache_hit_rate: number;
  };
  performance: {
    avg_execution_time_seconds: number;
  };
  artifacts: {
    total: number;
  };
}

export default function RunsPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);

  const token = typeof window !== "undefined"
    ? localStorage.getItem("token") : null;
  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const res = await fetch(`${API}/system/metrics`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        setMetrics(data);
      } finally {
        setLoading(false);
      }
    };
    fetch_();
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-gray-400 text-sm">Loading system metrics...</div>
    </div>
  );

  if (!metrics) return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <p className="text-gray-500">Failed to load metrics.</p>
    </div>
  );

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Execution Monitor</h1>

      {/* Execution Counts */}
      <div className="grid grid-cols-4 gap-4">
        <StatBox label="Total Runs" value={metrics.executions.total} />
        <StatBox label="Success" value={metrics.executions.success} color="green" />
        <StatBox label="Fallback" value={metrics.executions.fallback} color="yellow" />
        <StatBox label="Failed" value={metrics.executions.failed} color="red" />
      </div>

      {/* Rates */}
      <div className="rounded-xl border border-gray-200 p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          System Rates
        </h2>
        <div className="space-y-3">
          <RateRow
            label="Success Rate"
            value={metrics.rates.success_rate}
            color="green"
          />
          <RateRow
            label="Fallback Rate"
            value={metrics.rates.fallback_rate}
            color="yellow"
          />
          <RateRow
            label="Cache Hit Rate"
            value={metrics.rates.cache_hit_rate}
            color="indigo"
          />
        </div>
      </div>

      {/* Performance */}
      <div className="rounded-xl border border-gray-200 p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">
          Performance
        </h2>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Avg Execution Time</span>
          <span className="font-semibold text-gray-800">
            {metrics.performance.avg_execution_time_seconds}s
          </span>
        </div>
        <div className="flex justify-between text-sm mt-2">
          <span className="text-gray-500">Total Artifacts Stored</span>
          <span className="font-semibold text-gray-800">
            {metrics.artifacts.total}
          </span>
        </div>
      </div>
    </div>
  );
}

function StatBox({
  label,
  value,
  color = "gray"
}: {
  label: string;
  value: number;
  color?: "green" | "yellow" | "red" | "gray";
}) {
  const colors = {
    green: "text-green-700 bg-green-50 border-green-200",
    yellow: "text-yellow-700 bg-yellow-50 border-yellow-200",
    red: "text-red-700 bg-red-50 border-red-200",
    gray: "text-gray-700 bg-gray-50 border-gray-200",
  };

  return (
    <div className={`rounded-xl border p-4 ${colors[color]}`}>
      <p className="text-xs font-medium mb-1 opacity-70">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

function RateRow({
  label,
  value,
  color
}: {
  label: string;
  value: number;
  color: "green" | "yellow" | "indigo";
}) {
  const percent = Math.round(value * 100);
  const barColor = {
    green: "bg-green-500",
    yellow: "bg-yellow-500",
    indigo: "bg-indigo-500",
  }[color];

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium text-gray-800">{percent}%</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} rounded-full`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}