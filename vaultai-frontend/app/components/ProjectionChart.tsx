"use client";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer,
} from "recharts";
import type { ProjectionDataPoint } from "../../lib/types/plans";

function fmt(n: number) {
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
  if (n >= 1000)   return `₹${(n / 1000).toFixed(0)}K`;
  return `₹${n}`;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div style={{ background: "#22263A", border: "1px solid #2E3248", borderRadius: 8, padding: "10px 14px", fontSize: 12 }}>
      <p style={{ margin: "0 0 6px", fontWeight: 600, color: "#F1F5F9" }}>Month {label}</p>
      <p style={{ margin: "0 0 2px", color: "#6366F1" }}>Balance: {fmt(d.balance)}</p>
      <p style={{ margin: "0 0 2px", color: "#22C55E" }}>Growth: {fmt(d.growth)}</p>
      <p style={{ margin: 0, color: "#94A3B8" }}>Contributed: {fmt(d.contribution)}</p>
    </div>
  );
}

export default function ProjectionChart({
  data,
  targetAmount,
  label,
}: {
  data: ProjectionDataPoint[];
  targetAmount?: number;
  label?: string;
}) {
  return (
    <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, padding: 24 }}>
      {label && (
        <p style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 20px" }}>
          {label}
        </p>
      )}
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#2E3248" strokeDasharray="3 3" />
          <XAxis
            dataKey="month"
            tick={{ fill: "#475569", fontSize: 11 }}
            axisLine={{ stroke: "#2E3248" }}
            tickLine={false}
            label={{ value: "Month", position: "insideBottom", offset: -2, fill: "#475569", fontSize: 11 }}
          />
          <YAxis
            tickFormatter={fmt}
            tick={{ fill: "#475569", fontSize: 11 }}
            axisLine={{ stroke: "#2E3248" }}
            tickLine={false}
            width={60}
          />
          <Tooltip content={<CustomTooltip />} />
          {targetAmount && (
            <ReferenceLine
              y={targetAmount}
              stroke="#F59E0B"
              strokeDasharray="6 3"
              label={{ value: "Target", fill: "#F59E0B", fontSize: 11, position: "right" }}
            />
          )}
          <Line
            type="monotone"
            dataKey="balance"
            stroke="#6366F1"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "#6366F1" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}