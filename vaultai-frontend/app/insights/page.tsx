"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getInsights, runInsights, getExecution } from "../../lib/backend";
import type { InsightResponse } from "../../lib/backend";
import InsightCard from "../components/InsightCard";
import { RefreshButton } from "../components/RefreshButton";
import { EmptyState } from "../components/EmptyState";
import { ExecutionTimeline } from "../components/ExecutionTimeline";

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

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Spending Intelligence</h1>
          <p className="text-sm text-gray-600 mt-1">AI-powered financial analysis</p>
        </div>
        <RefreshButton onClick={handleRefresh} loading={refreshing} />
      </div>

      {refreshing && <ExecutionTimeline status="running" executionId={executionId} />}

      {status === "stale" && !refreshing && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
          ⚠️ Data changed. Click Refresh for updated insights.
        </div>
      )}

      {status === "error" && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          ⚠️ Failed to load. Please try again.
        </div>
      )}

      {status === "loading" && (
        <div className="bg-white rounded-lg border p-6 animate-pulse">
          <div className="flex justify-between mb-4">
            <div className="space-y-2">
              <div className="h-4 w-36 bg-gray-200 rounded" />
              <div className="h-3 w-24 bg-gray-200 rounded" />
            </div>
            <div className="w-16 h-16 bg-gray-200 rounded-full" />
          </div>
          <div className="h-20 bg-gray-200 rounded mb-4" />
        </div>
      )}

      {status === "unavailable" && !refreshing && (
        <EmptyState
          title="No insights yet"
          description="Add expenses and generate your first insight."
          action={{ label: "Generate Insight", onClick: handleRefresh, loading: refreshing }}
        />
      )}

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
    </div>
  );
}
