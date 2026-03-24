'use client';
import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Calendar, AlertTriangle, Target } from 'lucide-react';
import AuthenticatedLayout from '../../components/Authenticatedlayout';
import GraphExecutionTrace from '../../components/GraphExecutionTrace';
import AssumptionsBlock from '../../components/AssumptionsBlock';
import { formatIndianCurrency, getRelativeTime } from '../../../lib/planUtils';
import { getPlan, ApiError } from '../../../lib/backend';

// Raw backend PlanDetailResponse — no frontend type mapping
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

const FEASIBILITY_COLOR: Record<string, string> = {
  FEASIBLE:   '#10B981',
  STRETCH:    '#F59E0B',
  INFEASIBLE: '#EF4444',
};

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

// Simple coverage bar
function CoverageBar({ ratio, color }: { ratio: number; color: string }) {
  const pct = Math.min(Math.round(ratio * 100), 100);
  return (
    <div style={{ height: 8, borderRadius: 4, background: '#2E3248', overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 4, transition: 'width 0.4s ease' }} />
    </div>
  );
}

export default function GoalPlanPage() {
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
    <AuthenticatedLayout title="Goal Plan">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
        <p style={{ fontSize: 13, color: '#475569' }}>Loading plan…</p>
      </div>
    </AuthenticatedLayout>
  );

  if (error || !plan) return (
    <AuthenticatedLayout title="Goal Plan">
      <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 12, padding: 32, textAlign: 'center' }}>
        <p style={{ fontSize: 14, color: '#EF4444', margin: 0 }}>{error ?? 'Plan not found.'}</p>
      </div>
    </AuthenticatedLayout>
  );

  // ── Pull directly from projected_outcomes (real backend keys) ─────────────
  const o    = plan.projected_outcomes ?? {};
  const asmp = plan.assumptions        ?? {};
  const conf = plan.confidence         ?? {};

  const goalType        = String(o.goal_type        ?? asmp.goal_type     ?? '—');
  const targetAmount    = Number(o.target_amount    ?? asmp.target_amount ?? 0);
  const horizonMonths   = Number(o.horizon_months   ?? asmp.horizon_months ?? 0);
  const projectedBalance= Number(o.projected_balance ?? 0);
  const coverageRatio   = Number(o.coverage_ratio   ?? 0);
  const gapAmount       = Number(o.gap_amount       ?? 0);
  const surplus         = Number(o.surplus          ?? 0);
  const monthsToGoal    = o.months_to_goal != null ? Number(o.months_to_goal) : null;
  const feasibilityLabel= String(o.feasibility_label ?? 'FEASIBLE').toUpperCase();
  const contribRequired = Number(o.contribution_required ?? 0);
  const overallConf     = Number(conf.overall ?? 0);

  // Debt-specific fields
  const isDebt         = goalType === 'debt';
  const totalMonths    = Number(o.total_months    ?? 0);
  const totalInterest  = Number(o.total_interest_paid ?? 0);
  const payoffSchedule = Array.isArray(o.payoff_schedule) ? (o.payoff_schedule as Record<string, unknown>[]) : [];

  const fColor   = FEASIBILITY_COLOR[feasibilityLabel] ?? '#6366F1';
  const goalTitle = goalType.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());

  return (
    <AuthenticatedLayout title="Goal Plan">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* ── Header ── */}
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: 'rgba(16,185,129,0.15)', color: '#10B981' }}>
                Goal Plan
              </span>
              <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: `${fColor}18`, color: fColor }}>
                {feasibilityLabel}
              </span>
              {plan.degraded && (
                <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(245,158,11,0.15)', color: '#F59E0B' }}>
                  Degraded
                </span>
              )}
            </div>
            {plan.created_at && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94A3B8' }}>
                <Calendar size={12} /> {getRelativeTime(plan.created_at)}
              </div>
            )}
          </div>
          <div>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', margin: '0 0 6px' }}>{goalTitle}</h2>
            {targetAmount > 0 && (
              <p style={{ fontSize: 13, color: '#CBD5E1', margin: 0 }}>
                Target: <strong>{formatIndianCurrency(targetAmount)}</strong>
                {horizonMonths > 0 && <> in <strong>{horizonMonths} months</strong></>}
              </p>
            )}
          </div>
        </div>

        {/* ── Summary cards ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          {[
            { label: 'Target Amount',    value: formatIndianCurrency(targetAmount),              color: '#6366F1', icon: Target   },
            { label: 'Time Horizon',     value: horizonMonths > 0 ? `${horizonMonths} mo` : '—', color: '#10B981', icon: Calendar },
            { label: 'Coverage',         value: `${Math.round(coverageRatio * 100)}%`,           color: fColor,    icon: Target   },
          ].map(({ label, value, color, icon: Icon }) => (
            <div key={label} style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <Icon size={13} color={color} />
                <p style={{ fontSize: 11, color: '#94A3B8', margin: 0 }}>{label}</p>
              </div>
              <p style={{ fontSize: 20, fontWeight: 800, color, margin: 0, fontFamily: 'monospace' }}>{value}</p>
            </div>
          ))}
        </div>

        {/* ── Coverage bar + gap/surplus ── */}
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <p style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.07em', margin: 0 }}>Goal Progress</p>
            {overallConf > 0 && (
              <span style={{ fontFamily: 'monospace', fontSize: 12, color: overallConf >= 0.7 ? '#22C55E' : '#F59E0B', fontWeight: 700 }}>
                {Math.round(overallConf * 100)}% confidence
              </span>
            )}
          </div>
          <CoverageBar ratio={coverageRatio} color={fColor} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10 }}>
            <span style={{ fontSize: 12, color: '#64748B' }}>
              Projected: <span style={{ color: '#F1F5F9', fontWeight: 600, fontFamily: 'monospace' }}>{formatIndianCurrency(projectedBalance)}</span>
            </span>
            {gapAmount > 0 && (
              <span style={{ fontSize: 12, color: '#EF4444' }}>
                Gap: <span style={{ fontWeight: 600, fontFamily: 'monospace' }}>{formatIndianCurrency(gapAmount)}</span>
              </span>
            )}
            {surplus > 0 && (
              <span style={{ fontSize: 12, color: '#10B981' }}>
                Surplus: <span style={{ fontWeight: 600, fontFamily: 'monospace' }}>{formatIndianCurrency(surplus)}</span>
              </span>
            )}
          </div>
        </div>

        {/* ── Key details ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {contribRequired > 0 && (
            <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 18 }}>
              <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Required Monthly</p>
              <p style={{ fontSize: 22, fontWeight: 800, color: '#6366F1', margin: 0, fontFamily: 'monospace' }}>{formatIndianCurrency(contribRequired)}</p>
            </div>
          )}
          {monthsToGoal != null && (
            <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 18 }}>
              <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Months to Goal</p>
              <p style={{ fontSize: 22, fontWeight: 800, color: '#10B981', margin: 0, fontFamily: 'monospace' }}>{monthsToGoal}</p>
            </div>
          )}
        </div>

        {/* ── Infeasible warning ── */}
        {feasibilityLabel === 'INFEASIBLE' && (
          <div style={{ padding: 16, borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <AlertTriangle size={18} color="#EF4444" style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <p style={{ fontSize: 13, fontWeight: 600, color: '#EF4444', margin: '0 0 4px' }}>Goal may not be achievable within the given horizon</p>
              <p style={{ fontSize: 12, color: '#CBD5E1', margin: 0 }}>
                Consider increasing monthly savings to {formatIndianCurrency(contribRequired)}, extending the horizon, or reducing the target.
              </p>
            </div>
          </div>
        )}

        {/* ── Debt payoff table ── */}
        {isDebt && payoffSchedule.length > 0 && (
          <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, overflow: 'hidden' }}>
            <div style={{ padding: '12px 20px', background: '#0F1117', borderBottom: '1px solid #2E3248', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <p style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>
                Debt Payoff Schedule
              </p>
              <div style={{ display: 'flex', gap: 16 }}>
                {totalMonths > 0 && <span style={{ fontSize: 12, color: '#94A3B8' }}>{totalMonths} months</span>}
                {totalInterest > 0 && <span style={{ fontSize: 12, color: '#EF4444' }}>Interest: {formatIndianCurrency(totalInterest)}</span>}
              </div>
            </div>
            <div style={{ overflowX: 'auto', maxHeight: 320, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead style={{ position: 'sticky', top: 0, background: '#1A1D27' }}>
                  <tr style={{ borderBottom: '1px solid #2E3248' }}>
                    {['Month', 'Opening', 'Interest', 'Principal', 'Closing'].map((h) => (
                      <th key={h} style={{ padding: '10px 16px', textAlign: h === 'Month' ? 'left' : 'right', fontSize: 11, fontWeight: 600, color: '#475569', textTransform: 'uppercase' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {payoffSchedule.map((row, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid #1E2235' }}>
                      <td style={{ padding: '10px 16px', fontSize: 13, color: '#F1F5F9' }}>{String(row.month ?? idx + 1)}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'right', fontSize: 13, color: '#94A3B8', fontFamily: 'monospace' }}>{formatIndianCurrency(Number(row.opening_balance ?? 0))}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'right', fontSize: 13, color: '#EF4444', fontFamily: 'monospace' }}>{formatIndianCurrency(Number(row.interest ?? 0))}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'right', fontSize: 13, color: '#10B981', fontFamily: 'monospace' }}>{formatIndianCurrency(Number(row.principal ?? 0))}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'right', fontSize: 13, color: '#F1F5F9', fontFamily: 'monospace', fontWeight: 600 }}>{formatIndianCurrency(Number(row.closing_balance ?? 0))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── AI Narration ── */}
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