import Link from 'next/link';
import StatusBadge from './StatusBadge';
import { Insight } from '@/lib/api';

export default function InsightCard({ insight }: { insight: Insight }) {
  const isLowConfidence = insight.confidence < 0.4;

  return (
    <Link href={`/insights/${insight.id}`}>
      <div className={`p-4 border rounded-lg transition-all hover:shadow-md ${
        isLowConfidence ? 'opacity-60 bg-gray-50' : 'bg-white'
      }`}>
        <div className="flex justify-between items-start mb-2">
          <h3 className="font-semibold text-lg text-gray-900">{insight.type}</h3>
          <StatusBadge status={insight.status} />
        </div>
        <p className="text-gray-600 mb-4 line-clamp-2">{insight.summary}</p>
        <div className="flex justify-between items-center text-sm text-gray-500">
          <span>Confidence: {(insight.confidence * 100).toFixed(0)}%</span>
          <span>{new Date(insight.generatedAt).toLocaleDateString()}</span>
        </div>
      </div>
    </Link>
  );
}