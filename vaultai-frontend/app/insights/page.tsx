"use client";
import { useEffect, useState } from 'react';
import { getInsights, Insight } from '@/lib/api';
import InsightCard from '../components/InsightCard';
import RefreshButton from '../components/RefreshButton';
import EmptyState from '../components/EmptyState';

export default function InsightsPage() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchInsights = () => {
    getInsights().then(data => {
      setInsights(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { fetchInsights(); }, []);

  if (loading) return <div className="p-8">Loading insights...</div>;

  return (
    <div className="max-w-5xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">System Insights</h1>
        <RefreshButton onComplete={fetchInsights} />
      </div>

      {insights.length === 0 ? (
        <EmptyState message="No insights generated yet." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {insights.map(i => <InsightCard key={i.id} insight={i} />)}
        </div>
      )}
    </div>
  );
}