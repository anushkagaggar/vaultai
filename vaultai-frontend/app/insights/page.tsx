"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getInsights, runInsights, getExecution } from "../../lib/backend";
import type { InsightResponse } from "../../lib/backend";
import InsightCard from "../components/InsightCard";
import { RefreshButton } from "../components/RefreshButton";
import { EmptyState } from "../components/EmptyState";
import { ExecutionTimeline } from "../components/ExecutionTimeline";
import AuthenticatedLayout from "../components/Authenticatedlayout";

export default function InsightsPage() {
  const router = useRouter();
  const [insight, setInsight] = useState<InsightResponse | null>(null);
  const [status, setStatus] = useState<string>("loading");
  const [refreshing, setRefreshing] = useState(false);
  const [executionId, setExecutionId] = useState<number | null>(null);
  const pollingActive = { current: true };

  const fetchInsight = useCallback(async () => {
    try {
      console.log("=== FETCHING INSIGHT ===");
      console.log("API URL:", `${process.env.NEXT_PUBLIC_API_URL}/insights/trends`);
      
      const data = await getInsights();
      
      console.log("=== INSIGHT RESPONSE ===");
      console.log("Status:", data.status);
      console.log("Degraded:", data.degraded);
      console.log("Confidence:", data.confidence);
      console.log("Has data:", !!data.data);
      console.log("Stable:", data.stable);
      console.log("Execution required:", data.execution_required);
      console.log("Full response:", data);
      
      setStatus(data.status);
      setInsight(data.status === "ready" ? data : null);
    } catch (error: any) {
      console.error("Fetch insight error:", error);
      if (error.message === "unauthorized") {
        router.push("/auth");
      } else {
        setStatus("error");
      }
    }
  }, [router]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    
    try {
      console.log("Starting insight computation...");
      const data = await runInsights();
      console.log("Run insight response:", data);

      // ✅ Check if execution_id exists
      if (data.execution_id) {
        setExecutionId(data.execution_id);

        // ✅ Polling function
        const poll = async () => {
          if (!pollingActive.current) return;

          try {
            const execData = await getExecution(data.execution_id);
            console.log("Execution poll:", execData);

            // ✅ Check terminal status
            if (execData.is_terminal) {
              console.log("Execution completed, refreshing insight...");
              setRefreshing(false);
              setExecutionId(null);
              
              // ✅ Wait a bit for artifact to be created
              await new Promise(resolve => setTimeout(resolve, 500));
              
              // ✅ Fetch the new insight
              await fetchInsight();
            } else {
              console.log("Still running, polling again...");
              setTimeout(poll, 2500);
            }
          } catch (error) {
            console.error("Polling error:", error);
            setRefreshing(false);
          }
        };

        // ✅ Start polling immediately
        poll();
        
      } else if (data.status === "completed") {
        // ✅ If already completed, just refresh
        console.log("Already completed, fetching insight...");
        setRefreshing(false);
        await fetchInsight();
      } else {
        console.warn("Unexpected response:", data);
        setRefreshing(false);
        setStatus("error");
      }
    } catch (error: any) {
      console.error("Run insight error:", error);
      if (error.message === "unauthorized") {
        router.push("/auth");
      } else {
        setRefreshing(false);
        setStatus("error");
      }
    }
  }, [fetchInsight, router]);

  useEffect(() => {
    fetchInsight();
    return () => { pollingActive.current = false; };
  }, [fetchInsight]);

  // ── UI ────────────────────────────────────────────────────────────
  return (
    <AuthenticatedLayout
      title="Spending Intelligence"
      action={<RefreshButton onClick={handleRefresh} loading={refreshing} />}
    >
      {/* Execution timeline while refreshing */}
      {refreshing && (
        <ExecutionTimeline status="running" executionId={executionId} />
      )}

      {status === "stale" && !refreshing && (
        <div
          style={{
            marginBottom: 16,
            padding: "12px 16px",
            background: "rgba(245,158,11,0.08)",
            border: "1px solid rgba(245,158,11,0.2)",
            borderRadius: 10,
            fontSize: 13,
            color: "#F59E0B",
          }}
        >
          ⚠ Your expense data changed. Click Refresh for updated insights.
        </div>
      )}

      {/* Error banner */}
      {status === "error" && (
        <div
          style={{
            marginBottom: 16,
            padding: "12px 16px",
            background: "rgba(239,68,68,0.08)",
            border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 10,
            fontSize: 13,
            color: "#EF4444",
          }}
        >
          ⚠ Failed to load insights. Please try again.
        </div>
      )}

      {/* Loading skeleton */}
      {status === "loading" && (
        <div
          style={{
            background: "#1A1D27",
            border: "1px solid #2E3248",
            borderRadius: 14,
            padding: 24,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
            <div>
              <div style={{ height: 16, width: 160, background: "#22263A", borderRadius: 6, marginBottom: 8 }} />
              <div style={{ height: 12, width: 100, background: "#22263A", borderRadius: 6 }} />
            </div>
            <div style={{ width: 80, height: 60, background: "#22263A", borderRadius: 10 }} />
          </div>
          <div style={{ height: 80, background: "#22263A", borderRadius: 10, marginBottom: 16 }} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
            {[1,2,3,4].map((i) => (
              <div key={i} style={{ height: 64, background: "#22263A", borderRadius: 10 }} />
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {status === "unavailable" && !refreshing && (
        <EmptyState
          title="No insights yet"
          description="Add some expenses and generate your first AI insight."
          action={{ label: "Generate Insight", onClick: handleRefresh, loading: refreshing }}
        />
      )}

      {/* Insight card */}
      {insight && insight.data && (
        <InsightCard
          insight={{
            artifact_id: insight.artifact_id,
            confidence: insight.confidence ?? 0,
            degraded: insight.degraded ?? false,
            data: insight.data,
            created_at: insight.created_at,
          }}
        />
      )}
    </AuthenticatedLayout>
  );
}