'use client';
import { Suspense } from 'react';
import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Calendar } from 'lucide-react';
import AuthenticatedLayout from '../../components/Authenticatedlayout';
import PlanConfidence from '../../components/PlanConfidence';
import GraphExecutionTrace from '../../components/GraphExecutionTrace';
import AssumptionsBlock from '../../components/AssumptionsBlock';
import { formatIndianCurrency, getRelativeTime } from '../../../lib/planUtils';
import { getPlan, ApiError } from '../../../lib/backend';

interface RawPlan {
  plan_id:            number | null;
  plan_type:          string;
  projected_outcomes: Record<string, unknown> | null;
  explanation:        string | null;
  confidence:         Record<string, unknown> | null;
  degraded:           boolean;
  graph_trace:        string[];
  status:             string;
  assumptions:        Record<string, unknown> | null;
  created_at:         string | null;
}

const ALLOC_COLORS = { equity: '#6366F1', debt: '#F59E0B', liquid: '#14B8A6' } as const;
const FRESH_COLOR: Record<string, string>  = { live: '#10B981', cached: '#F59E0B', fallback: '#EF4444' };
const FRESH_LABEL: Record<string, string>  = { live: 'Live Data', cached: 'Cached', fallback: 'Fallback' };

function AllocBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ height: 6, borderRadius: 3, background: '#2E3248', overflow: 'hidden', flex: 1 }}>
      <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: color, borderRadius: 3, transition: 'width 0.4s ease' }} />
    </div>
  );
}

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

function InvestPlanContent() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const planId       = searchParams.get('id');

  const [plan,    setPlan]    = useState<RawPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    if (!planId) { setError('No plan ID in URL.'); setLoading(false); return; }
    getPlan(planId)
      .then((data) => setPlan(data as unknown as RawPlan))
      .catch((e: ApiError) => {
        if (e.status === 401) router.push('/auth');
        else setError(e.detail ?? e.message ?? 'Failed to load plan.');
      })
      .finally(() => setLoading(false));
  }, [planId, router]);

  if (loading) return (
    <AuthenticatedLayout title="Investment Plan">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
        <p style={{ fontSize: 13, color: '#475569' }}>Loading plan…</p>
      </div>
    </AuthenticatedLayout>
  );

  if (error || !plan) return (
    <AuthenticatedLayout title="Investment Plan">
      <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 12, padding: 32, textAlign: 'center' }}>
        <p style={{ fontSize: 14, color: '#EF4444', margin: 0 }}>{error ?? 'Plan not found.'}</p>
      </div>
    </AuthenticatedLayout>
  );

  const o    = plan.projected_outcomes  ?? {};
  const asmp = plan.assumptions         ?? {};
  const conf = plan.confidence          ?? {};

  const riskProfile      = String(o.risk_profile      ?? asmp.risk_profile     ?? '—');
  const investmentAmount = Number(asmp.investment_amount ?? o.total_allocated  ?? 0);
  const totalAllocated   = Number(o.total_allocated   ?? investmentAmount);

  const equityPct  = Number(o.equity_pct   ?? 0);
  const debtPct    = Number(o.debt_pct     ?? 0);
  const liquidPct  = Number(o.liquid_pct   ?? 0);
  const equityAmt  = Number(o.equity_amount ?? 0);
  const debtAmt    = Number(o.debt_amount   ?? 0);
  const liquidAmt  = Number(o.liquid_amount ?? 0);

  const overallConf   = Number(conf.overall           ?? 0);
  const externalFresh = String(conf.external_freshness ?? conf.externalFreshness ?? 'fallback');
  const freshColor    = FRESH_COLOR[externalFresh] ?? '#EF4444';

  const allocRows = [
    { label: 'Equity', pct: equityPct, amount: equityAmt, color: ALLOC_COLORS.equity },
    { label: 'Debt',   pct: debtPct,   amount: debtAmt,   color: ALLOC_COLORS.debt   },
    { label: 'Liquid', pct: liquidPct, amount: liquidAmt, color: ALLOC_COLORS.liquid },
  ];

  const RISK_COLOR: Record<string, string> = { conservative: '#10B981', moderate: '#F59E0B', aggressive: '#EF4444' };
  const riskColor = RISK_COLOR[riskProfile.toLowerCase()] ?? '#6366F1';

  return (
    <AuthenticatedLayout title="Investment Plan">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: 'rgba(139,92,246,0.15)', color: '#8B5CF6' }}>
                Investment Plan
              </span>
              <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: plan.degraded ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.15)', color: plan.degraded ? '#F59E0B' : '#10B981' }}>
                {plan.degraded ? 'Degraded' : 'Validated'}
              </span>
            </div>
            {plan.created_at && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94A3B8' }}>
                <Calendar size={12} /> {getRelativeTime(plan.created_at)}
              </div>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'start' }}>
            <div>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', margin: '0 0 6px' }}>Investment Allocation</h2>
              <p style={{ fontSize: 13, color: '#CBD5E1', margin: 0 }}>
                Optimised portfolio for a{' '}
                <span style={{ color: riskColor, fontWeight: 600 }}>{riskProfile}</span> risk profile
              </p>
            </div>
            {overallConf > 0 && (
              <div style={{ textAlign: 'right' }}>
                <p style={{ fontSize: 10, color: '#475569', margin: '0 0 4px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Confidence</p>
                <p style={{ fontSize: 22, fontWeight: 800, fontFamily: 'monospace', color: overallConf >= 0.7 ? '#22C55E' : overallConf >= 0.4 ? '#F59E0B' : '#EF4444', margin: 0 }}>
                  {Math.round(overallConf * 100)}%
                </p>
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 20 }}>
            <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Investment Amount</p>
            <p style={{ fontSize: 26, fontWeight: 800, color: '#6366F1', margin: 0, fontFamily: 'monospace' }}>
              {formatIndianCurrency(investmentAmount)}
            </p>
          </div>
          <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 20 }}>
            <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Risk Profile</p>
            <p style={{ fontSize: 26, fontWeight: 800, color: riskColor, margin: 0, textTransform: 'capitalize' }}>
              {riskProfile}
            </p>
          </div>
        </div>

        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '12px 20px', background: '#0F1117', borderBottom: '1px solid #2E3248' }}>
            <p style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>
              Allocation Breakdown
            </p>
          </div>
          {allocRows.map(({ label, pct, amount, color }) => (
            <div key={label} style={{ padding: '16px 20px', borderBottom: '1px solid #1E2235' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
                  <span style={{ fontSize: 14, fontWeight: 500, color: '#F1F5F9' }}>{label}</span>
                </div>
                <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color, fontFamily: 'monospace' }}>{pct.toFixed(0)}%</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#F1F5F9', fontFamily: 'monospace', minWidth: 80, textAlign: 'right' }}>
                    {formatIndianCurrency(amount)}
                  </span>
                </div>
              </div>
              <AllocBar pct={pct} color={color} />
            </div>
          ))}
          <div style={{ padding: '12px 20px', display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#64748B' }}>Total Allocated</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#F1F5F9', fontFamily: 'monospace' }}>
              {formatIndianCurrency(totalAllocated)}
            </span>
          </div>
        </div>

        {Number(asmp.horizon_months) > 0 && (
          <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 20 }}>
            <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Investment Horizon</p>
            <p style={{ fontSize: 20, fontWeight: 700, color: '#F1F5F9', margin: 0 }}>
              {Number(asmp.horizon_months)} months
              <span style={{ fontSize: 13, color: '#64748B', fontWeight: 400, marginLeft: 8 }}>
                ({(Number(asmp.horizon_months) / 12).toFixed(1)} years)
              </span>
            </p>
          </div>
        )}

        <div style={{ padding: '12px 16px', borderRadius: 10, background: `${freshColor}10`, border: `1px solid ${freshColor}30`, display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: freshColor, flexShrink: 0 }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: freshColor }}>
            {FRESH_LABEL[externalFresh] ?? externalFresh}
          </span>
          <span style={{ fontSize: 12, color: '#94A3B8' }}>Market data freshness</span>
        </div>

        {plan.explanation && (
          <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
            <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 99, background: 'rgba(99,102,241,0.15)', color: '#A5B4FC', fontWeight: 600 }}>
              AI Narration
            </span>
            <p style={{ fontSize: 14, color: '#CBD5E1', margin: '12px 0 0', lineHeight: 1.7 }}>{plan.explanation}</p>
          </div>
        )}

        <GraphExecutionTrace nodes={toGraphNodes(plan.graph_trace ?? [])} validationStatus={plan.status === 'validated' ? 'validated' : 'fallback'} />
        <AssumptionsBlock assumptions={plan.assumptions ?? {}} />
      </div>
    </AuthenticatedLayout>
  );
}

export default function InvestPlanPage() {
  return (
    <Suspense fallback={<div style={{ padding: 48, textAlign: 'center', color: '#475569', fontSize: 13 }}>Loading...</div>}>
      <InvestPlanContent />
    </Suspense>
  );
}