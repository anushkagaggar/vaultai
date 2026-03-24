'use client';
import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Calendar, TrendingUp } from 'lucide-react';
import AuthenticatedLayout from '../../components/Authenticatedlayout';
import PlanConfidence from '../../components/PlanConfidence';
import GraphExecutionTrace from '../../components/GraphExecutionTrace';
import ProjectionChart from '../../components/ProjectionChart';
import ScenarioComparison from '../../components/ScenarioComparison';
import AssumptionsBlock from '../../components/AssumptionsBlock';
import { formatIndianCurrency, getRelativeTime } from '../../../lib/planUtils';
import { getPlan } from '../../../lib/backend';
import { ApiError } from '../../../lib/backend';

interface RawPlan {
  plan_id: number | null;
  plan_type: string;
  projected_outcomes: Record<string, unknown> | null;
  explanation: string | null;
  confidence: Record<string, unknown> | null;
  degraded: boolean;
  graph_trace: string[];
  status: string;
  assumptions: Record<string, unknown> | null;
  created_at: string | null;
}

// Backend graph_trace is string[] — convert to GraphNode[] for the component
function toGraphNodes(trace: string[]): import('../../../lib/types/plans').GraphNode[] {
  return trace.map((name) => ({
    name,
    type: name.includes('llm') || name.includes('explain') || name.includes('narrat')
      ? 'llm'
      : name.includes('valid') || name.includes('check')
      ? 'validation'
      : name.includes('persist') || name.includes('save') || name.includes('store')
      ? 'persist'
      : 'simulation',
    status:      'success' as const,
    description: name.replace(/_/g, ' '),
  }));
}

export default function BudgetPlanPage() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const planId       = searchParams.get('id');

  const [plan, setPlan] = useState<RawPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(false);

  useEffect(() => {
    if (!planId) { setError(true); setLoading(false); return; }
    getPlan(planId)
      .then((data) => setPlan(data as unknown as RawPlan))
      .catch((e: ApiError) => {
        if (e.status === 401) router.push('/auth');
        else setError(true);
      })
      .finally(() => setLoading(false));
  }, [planId, router]);

  if (loading) return (
    <AuthenticatedLayout title="Budget Plan">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
        <p style={{ fontSize: 13, color: '#475569' }}>Loading plan...</p>
      </div>
    </AuthenticatedLayout>
  );

  if (error || !plan) return (
    <AuthenticatedLayout title="Budget Plan">
      <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 12, padding: 32, textAlign: 'center' }}>
        <p style={{ fontSize: 14, color: '#EF4444', margin: 0 }}>Plan not found or failed to load.</p>
      </div>
    </AuthenticatedLayout>
  );

  // Extract from raw backend fields
  const o    = plan.projected_outcomes ?? {};
  const asmp = plan.assumptions        ?? {};
  const conf = plan.confidence         ?? {};

  const incomeMonthly  = Number(asmp.income_monthly   ?? o.income_monthly  ?? 0);
  const inflationRate  = Number(o.inflation_rate       ?? 0);
  const minSavingsRate = Number(o.savings_rate         ?? o.min_savings_rate ?? 0);
  const monthlySavings = Number(o.monthly_savings      ?? 0);
  const annualSavings  = Number(o.annual_savings       ?? 0);
  const overallConf    = Number(conf.overall           ?? 0);

  const hasScenarios = false; // budget_optimize is a stub — no scenarios yet


  return (
    <AuthenticatedLayout title="Budget Plan">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: 'rgba(59,130,246,0.15)', color: '#3B82F6' }}>Budget Plan</span>
              <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: plan.degraded ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.15)', color: plan.degraded ? '#F59E0B' : '#10B981' }}>
                {plan.degraded ? 'Degraded' : 'Validated'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94A3B8' }}>
              <Calendar size={12} /> {plan.created_at ? getRelativeTime(plan.created_at) : '—'}
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'start' }}>
            <div>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', margin: '0 0 6px' }}>Monthly Budget Plan</h2>
              <p style={{ fontSize: 13, color: '#CBD5E1', margin: 0 }}>Based on your income of {formatIndianCurrency(incomeMonthly)}/month</p>
            </div>
            {overallConf > 0 && <PlanConfidence confidence={{ overall: overallConf, dataCoverage: Number(conf.data_coverage ?? overallConf), assumptionRisk: (conf.assumption_risk ?? conf.assumptionRisk ?? 'low') as import('../../../lib/types/plans').AssumptionRisk, externalFreshness: (conf.external_freshness ?? conf.externalFreshness ?? 'fallback') as import('../../../lib/types/plans').ExternalFreshness }} />}
          </div>
        </div>

        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
          <p style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 16px' }}>Key Parameters</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>
            {[
              { label: 'Monthly Income',   value: formatIndianCurrency(incomeMonthly) },
              { label: 'Inflation Rate',   value: `${(inflationRate * 100).toFixed(1)}%` },
              { label: 'Min Savings Rate', value: `${(minSavingsRate * 100).toFixed(0)}%` },
            ].map(({ label, value }) => (
              <div key={label}>
                <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 4px' }}>{label}</p>
                <p style={{ fontSize: 18, fontWeight: 700, color: '#F1F5F9', margin: 0, fontFamily: 'monospace' }}>{value}</p>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {[
            { label: 'Monthly Savings', value: monthlySavings, sub: incomeMonthly > 0 ? `${((monthlySavings / incomeMonthly) * 100).toFixed(1)}% of income` : '—', color: '#10B981' },
            { label: 'Annual Savings',  value: annualSavings, sub: 'Projected for 12 months', color: '#6366F1' },
          ].map(({ label, value, sub, color }) => (
            <div key={label} style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                <TrendingUp size={14} color={color} />
                <p style={{ fontSize: 11, color: '#94A3B8', margin: 0 }}>{label}</p>
              </div>
              <p style={{ fontSize: 28, fontWeight: 800, color, margin: '0 0 4px', fontFamily: 'monospace' }}>{formatIndianCurrency(value)}</p>
              <p style={{ fontSize: 11, color: '#64748B', margin: 0 }}>{sub}</p>
            </div>
          ))}
        </div>

        {false && <ProjectionChart data={[]} label="12-Month Savings Projection" />}
        

        {plan.explanation && (
          <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
            <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 99, background: 'rgba(99,102,241,0.15)', color: '#A5B4FC', fontWeight: 600 }}>AI Narration</span>
            <p style={{ fontSize: 14, color: '#CBD5E1', margin: '12px 0 0', lineHeight: 1.7 }}>{plan.explanation}</p>
          </div>
        )}

        <GraphExecutionTrace nodes={toGraphNodes(plan.graph_trace ?? [])} validationStatus={plan.status === 'validated' ? 'validated' : 'fallback'} />
        <AssumptionsBlock assumptions={plan.assumptions ?? {}} />
      </div>
    </AuthenticatedLayout>
  );
}