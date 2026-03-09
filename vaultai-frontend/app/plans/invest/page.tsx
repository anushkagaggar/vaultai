'use client';
import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Calendar } from 'lucide-react';
import AuthenticatedLayout from '../../components/Authenticatedlayout';
import PlanConfidence from '../../components/PlanConfidence';
import GraphExecutionTrace from '../../components/GraphExecutionTrace';
import AllocationWheel from '../../components/AllocationWheel';
import AssumptionsBlock from '../../components/AssumptionsBlock';
import { formatIndianCurrency, getRelativeTime } from '../../../lib/planUtils';
import { getPlan } from '../../../lib/backend';
import type { InvestPlan } from '../../../lib/types/plans';

const FRESH_COLOR: Record<string, string> = { live: '#10B981', cached: '#F59E0B', fallback: '#EF4444' };
const FRESH_LABEL: Record<string, string> = { live: 'Live Data', cached: 'Cached', fallback: 'Fallback' };

export default function InvestPlanPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const planId = searchParams.get('id');

  const [plan, setPlan] = useState<InvestPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!planId) { setError(true); setLoading(false); return; }
    getPlan(planId)
      .then((data) => setPlan(data as InvestPlan))
      .catch((e: Error) => {
        if (e.message === 'unauthorized') router.push('/auth');
        else setError(true);
      })
      .finally(() => setLoading(false));
  }, [planId, router]);

  if (loading) return (
    <AuthenticatedLayout title="Investment Plan">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
        <p style={{ fontSize: 13, color: '#475569' }}>Loading plan...</p>
      </div>
    </AuthenticatedLayout>
  );

  if (error || !plan) return (
    <AuthenticatedLayout title="Investment Plan">
      <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 12, padding: 32, textAlign: 'center' }}>
        <p style={{ fontSize: 14, color: '#EF4444', margin: 0 }}>Plan not found or failed to load.</p>
      </div>
    </AuthenticatedLayout>
  );

  const freshColor = FRESH_COLOR[plan.confidence.externalFreshness];

  return (
    <AuthenticatedLayout title="Investment Plan">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Header */}
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: 'rgba(139,92,246,0.15)', color: '#8B5CF6' }}>
                Investment Plan
              </span>
              <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: plan.validationStatus === 'validated' ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)', color: plan.validationStatus === 'validated' ? '#10B981' : '#F59E0B' }}>
                {plan.validationStatus === 'validated' ? 'Validated' : 'Fallback'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94A3B8' }}>
              <Calendar size={12} /> {getRelativeTime(plan.createdAt)}
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'start' }}>
            <div>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', margin: '0 0 6px' }}>Investment Allocation</h2>
              <p style={{ fontSize: 13, color: '#CBD5E1', margin: 0 }}>
                Optimized portfolio for your {plan.riskProfile.toLowerCase()} risk profile
              </p>
            </div>
            <PlanConfidence confidence={plan.confidence} />
          </div>
        </div>

        {/* Risk + Amount */}
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24, display: 'flex', justifyContent: 'space-between' }}>
          <div>
            <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 6px' }}>Risk Profile</p>
            <p style={{ fontSize: 24, fontWeight: 800, color: '#F1F5F9', margin: 0 }}>{plan.riskProfile}</p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 6px' }}>Monthly Investment</p>
            <p style={{ fontSize: 24, fontWeight: 800, color: '#6366F1', margin: 0, fontFamily: 'monospace' }}>
              {formatIndianCurrency(plan.monthlyAmount)}
            </p>
          </div>
        </div>

        <AllocationWheel
          equity={plan.allocation.equity}
          debt={plan.allocation.debt}
          liquid={plan.allocation.liquid}
          monthlyAmount={plan.monthlyAmount}
        />

        {/* Allocation table */}
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '12px 20px', background: '#0F1117', borderBottom: '1px solid #2E3248' }}>
            <p style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>
              Allocation Breakdown
            </p>
          </div>
          {[
            { label: 'Equity', pct: plan.allocation.equity, amount: plan.amounts.equity, color: '#6366F1' },
            { label: 'Debt',   pct: plan.allocation.debt,   amount: plan.amounts.debt,   color: '#F59E0B' },
            { label: 'Liquid', pct: plan.allocation.liquid, amount: plan.amounts.liquid, color: '#14B8A6' },
          ].map(({ label, pct, amount, color }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid #2E3248' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 12, height: 12, borderRadius: 3, background: color }} />
                <span style={{ fontSize: 14, fontWeight: 500, color: '#F1F5F9' }}>{label}</span>
              </div>
              <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
                <span style={{ fontSize: 13, color: '#A5B4FC', fontFamily: 'monospace' }}>{pct}%</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#F1F5F9', fontFamily: 'monospace', width: 80, textAlign: 'right' }}>
                  {formatIndianCurrency(amount)}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Freshness indicator */}
        <div style={{ padding: '12px 16px', borderRadius: 10, background: `${freshColor}10`, border: `1px solid ${freshColor}30`, display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: freshColor }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: freshColor }}>
            {FRESH_LABEL[plan.confidence.externalFreshness]}
          </span>
          <span style={{ fontSize: 12, color: '#94A3B8' }}>Market data freshness indicator</span>
        </div>

        {/* AI Narration */}
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
          <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 99, background: 'rgba(99,102,241,0.15)', color: '#A5B4FC', fontWeight: 600 }}>
            AI Narration
          </span>
          <p style={{ fontSize: 14, color: '#CBD5E1', margin: '12px 0 0', lineHeight: 1.7 }}>{plan.explanation}</p>
        </div>

        <GraphExecutionTrace nodes={plan.graphTrace} validationStatus={plan.validationStatus} />
        <AssumptionsBlock assumptions={plan.assumptions} />
      </div>
    </AuthenticatedLayout>
  );
}