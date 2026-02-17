"use client";
import { useState } from 'react';
import { runInsight, getExecution } from '@/lib/api';

export default function RefreshButton({ onComplete }: { onComplete?: () => void }) {
  const [isPolling, setIsPolling] = useState(false);

  const handleRefresh = async () => {
    setIsPolling(true);
    try {
      const { executionId } = await runInsight();
      
      // Polling mechanism
      const interval = setInterval(async () => {
        const status = await getExecution(executionId);
        if (['success', 'fallback', 'failed'].includes(status.status)) {
          clearInterval(interval);
          setIsPolling(false);
          if (onComplete) onComplete();
        }
      }, 2000); // Poll every 2 seconds
    } catch (error) {
      console.error("Failed to start refresh", error);
      setIsPolling(false);
    }
  };

  return (
    <button 
      onClick={handleRefresh} 
      disabled={isPolling}
      className={`px-4 py-2 rounded-md text-white font-medium ${
        isPolling ? 'bg-blue-300 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
      }`}
    >
      {isPolling ? 'Computing...' : 'Recompute Insights'}
    </button>
  );
}